import os
import subprocess
import sys
import gradio as gr
from assets.i18n.i18n import I18nAuto
from core import (
    run_preprocess_script,
    run_extract_script,
    run_train_script,
    run_index_script,
)
from rvc.configs.config import max_vram_gpu, get_gpu_info
from rvc.lib.utils import format_title

i18n = I18nAuto()
now_dir = os.getcwd()
sys.path.append(now_dir)

sup_audioext = {
    "wav",
    "mp3",
    "flac",
    "ogg",
    "opus",
    "m4a",
    "mp4",
    "aac",
    "alac",
    "wma",
    "aiff",
    "webm",
    "ac3",
}

# Custom Pretraineds
pretraineds_custom_path = os.path.join(
    now_dir, "rvc", "pretraineds", "pretraineds_custom"
)

pretraineds_custom_path_relative = os.path.relpath(pretraineds_custom_path, now_dir)

if not os.path.exists(pretraineds_custom_path_relative):
    os.makedirs(pretraineds_custom_path_relative)


def get_pretrained_list(suffix):
    return [
        os.path.join(dirpath, filename)
        for dirpath, _, filenames in os.walk(pretraineds_custom_path_relative)
        for filename in filenames
        if filename.endswith(".pth") and suffix in filename
    ]


pretraineds_list_d = get_pretrained_list("D")
pretraineds_list_g = get_pretrained_list("G")


def refresh_custom_pretraineds():
    return (
        {"choices": sorted(get_pretrained_list("G")), "__type__": "update"},
        {"choices": sorted(get_pretrained_list("D")), "__type__": "update"},
    )


# Dataset Creator
datasets_path = os.path.join(now_dir, "assets", "datasets")

if not os.path.exists(datasets_path):
    os.makedirs(datasets_path)

datasets_path_relative = os.path.relpath(datasets_path, now_dir)


def get_datasets_list():
    return [
        dirpath
        for dirpath, _, filenames in os.walk(datasets_path_relative)
        if any(filename.endswith(tuple(sup_audioext)) for filename in filenames)
    ]


def refresh_datasets():
    return {"choices": sorted(get_datasets_list()), "__type__": "update"}


# Drop Model
def save_drop_model(dropbox):
    if ".pth" not in dropbox:
        gr.Info(
            i18n(
                "The file you dropped is not a valid pretrained file. Please try again."
            )
        )
    else:
        file_name = os.path.basename(dropbox)
        pretrained_path = os.path.join(pretraineds_custom_path_relative, file_name)
        if os.path.exists(pretrained_path):
            os.remove(pretrained_path)
        os.rename(dropbox, pretrained_path)
        gr.Info(
            i18n(
                "Click the refresh button to see the pretrained file in the dropdown menu."
            )
        )
    return None


# Drop Dataset
def save_drop_dataset_audio(dropbox: str | list[str], dataset_name):
    if not dataset_name:
        gr.Info("Please enter a valid dataset name. Please try again.")
        return None, None
    else:
        files = dropbox if isinstance(dropbox, list) else [dropbox]
        for file in files:
            file_extension = os.path.splitext(file)[1][1:].lower()
            if file_extension not in sup_audioext:
                gr.Info("The file you dropped is not a valid audio file. Please try again.")
            else:
                dataset_name = format_title(dataset_name)
                audio_file = format_title(os.path.basename(file))
                dataset_path = os.path.join(now_dir, "assets", "datasets", dataset_name)
                if not os.path.exists(dataset_path):
                    os.makedirs(dataset_path)
                destination_path = os.path.join(dataset_path, audio_file)
                if os.path.exists(destination_path):
                    os.remove(destination_path)
                os.rename(file, destination_path)
                gr.Info(
                    i18n(
                        "The audio file has been successfully added to the dataset. Please click the preprocess button."
                    )
                )
                dataset_path = os.path.dirname(destination_path)
                relative_dataset_path = os.path.relpath(dataset_path, now_dir)

        return None, relative_dataset_path


# Train Tab
def train_tab():
    with gr.Accordion(i18n("Preprocess")):
        with gr.Row():
            with gr.Column():
                model_name = gr.Textbox(
                    label=i18n("Model Name"),
                    info=i18n("Name of the new model."),
                    placeholder=i18n("Enter model name"),
                    value="my-project",
                    interactive=True,
                )
                dataset_path = gr.Dropdown(
                    label=i18n("Dataset Path"),
                    info=i18n("Path to the dataset folder."),
                    # placeholder=i18n("Enter dataset path"),
                    choices=get_datasets_list(),
                    allow_custom_value=True,
                    interactive=True,
                )
                refresh_datasets_button = gr.Button(i18n("Refresh Datasets"))
                dataset_name = gr.Textbox(
                    label=i18n("Dataset Name"),
                    info=i18n("Name of the new dataset."),
                    placeholder=i18n("Enter dataset name"),
                    interactive=True,
                )
                upload_audio_dataset = gr.File(
                    label=i18n("Upload Audio Dataset"),
                    type="filepath",
                    file_count="multiple",
                    interactive=True,
                )

            with gr.Column():
                sampling_rate = gr.Radio(
                    label=i18n("Sampling Rate"),
                    info=i18n("The sampling rate of the audio files."),
                    choices=["32000", "40000", "48000"],
                    value="40000",
                    interactive=True,
                )

                rvc_version = gr.Radio(
                    label=i18n("RVC Version"),
                    info=i18n("The RVC version of the model."),
                    choices=["v1", "v2"],
                    value="v2",
                    interactive=True,
                )

        preprocess_output_info = gr.Textbox(
            label=i18n("Output Information"),
            info=i18n("The output information will be displayed here."),
            value="",
            max_lines=8,
            interactive=False,
        )

        with gr.Row():
            preprocess_button = gr.Button(i18n("Preprocess Dataset"))
            preprocess_button.click(
                run_preprocess_script,
                [model_name, dataset_path, sampling_rate],
                preprocess_output_info,
                api_name="preprocess_dataset",
            )

    with gr.Accordion(i18n("Extract")):
        with gr.Row():
            hop_length = gr.Slider(
                1,
                512,
                128,
                step=1,
                label=i18n("Hop Length"),
                info=i18n(
                    "Denotes the duration it takes for the system to transition to a significant pitch change. Smaller hop lengths require more time for inference but tend to yield higher pitch accuracy."
                ),
                interactive=True,
            )
        with gr.Row():
            with gr.Column():
                f0method = gr.Radio(
                    label=i18n("Pitch extraction algorithm"),
                    info=i18n(
                        "Pitch extraction algorithm to use for the audio conversion. The default algorithm is rmvpe, which is recommended for most cases."
                    ),
                    choices=["pm", "dio", "crepe", "crepe-tiny", "harvest", "rmvpe"],
                    value="rmvpe",
                    interactive=True,
                )

        extract_output_info = gr.Textbox(
            label=i18n("Output Information"),
            info=i18n("The output information will be displayed here."),
            value="",
            max_lines=8,
            interactive=False,
        )
        extract_button = gr.Button(i18n("Extract Features"))
        extract_button.click(
            run_extract_script,
            [model_name, rvc_version, f0method, hop_length, sampling_rate],
            extract_output_info,
            api_name="extract_features",
        )

    with gr.Accordion(i18n("Train")):
        with gr.Row():
            batch_size = gr.Slider(
                1,
                50,
                max_vram_gpu(0),
                step=1,
                label=i18n("Batch Size"),
                info=i18n(
                    "It's advisable to align it with the available VRAM of your GPU. A setting of 4 offers improved accuracy but slower processing, while 8 provides faster and standard results."
                ),
                interactive=True,
            )
            save_every_epoch = gr.Slider(
                1,
                100,
                10,
                step=1,
                label=i18n("Save Every Epoch"),
                info=i18n("Determine at how many epochs the model will saved at."),
                interactive=True,
            )
            total_epoch = gr.Slider(
                1,
                10000,
                500,
                step=1,
                label=i18n("Total Epoch"),
                info=i18n(
                    "Specifies the overall quantity of epochs for the model training process."
                ),
                interactive=True,
            )
        with gr.Row():
            pitch_guidance = gr.Checkbox(
                label=i18n("Pitch Guidance"),
                info=i18n(
                    "By employing pitch guidance, it becomes feasible to mirror the intonation of the original voice, including its pitch. This feature is particularly valuable for singing and other scenarios where preserving the original melody or pitch pattern is essential."
                ),
                value=True,
                interactive=True,
            )
            pretrained = gr.Checkbox(
                label=i18n("Pretrained"),
                info=i18n(
                    "Utilize pretrained models when training your own. This approach reduces training duration and enhances overall quality."
                ),
                value=True,
                interactive=True,
            )
            save_only_latest = gr.Checkbox(
                label=i18n("Save Only Latest"),
                info=i18n(
                    "Enabling this setting will result in the G and D files saving only their most recent versions, effectively conserving storage space."
                ),
                value=False,
                interactive=True,
            )
            save_every_weights = gr.Checkbox(
                label=i18n("Save Every Weights"),
                info=i18n(
                    "This setting enables you to save the weights of the model at the conclusion of each epoch."
                ),
                value=True,
                interactive=True,
            )
            custom_pretrained = gr.Checkbox(
                label=i18n("Custom Pretrained"),
                info=i18n(
                    "Utilizing custom pretrained models can lead to superior results, as selecting the most suitable pretrained models tailored to the specific use case can significantly enhance performance."
                ),
                value=False,
                interactive=True,
            )
            multiple_gpu = gr.Checkbox(
                label=i18n("GPU Settings"),
                info=(
                    i18n(
                        "Sets advanced GPU settings, recommended for users with better GPU architecture."
                    )
                ),
                value=False,
                interactive=True,
            )

        with gr.Row():
            with gr.Column(visible=False) as pretrained_custom_settings:
                with gr.Accordion(i18n("Pretrained Custom Settings")):
                    upload_pretrained = gr.File(
                        label=i18n("Upload Pretrained Model"),
                        type="filepath",
                        interactive=True,
                    )
                    refresh_custom_pretaineds_button = gr.Button(
                        i18n("Refresh Custom Pretraineds")
                    )
                    g_pretrained_path = gr.Dropdown(
                        label=i18n("Custom Pretrained G"),
                        info=i18n(
                            "Select the custom pretrained model for the generator."
                        ),
                        choices=sorted(pretraineds_list_g),
                        interactive=True,
                        allow_custom_value=True,
                    )
                    d_pretrained_path = gr.Dropdown(
                        label=i18n("Custom Pretrained D"),
                        info=i18n(
                            "Select the custom pretrained model for the discriminator."
                        ),
                        choices=sorted(pretraineds_list_d),
                        interactive=True,
                        allow_custom_value=True,
                    )
            with gr.Column(visible=False) as gpu_custom_settings:
                with gr.Accordion("GPU Settings"):
                    gpu = gr.Textbox(
                        label=i18n("GPU Number"),
                        info=i18n(
                            "Specify the number of GPUs you wish to utilize for training by entering them separated by hyphens (-)."
                        ),
                        placeholder=i18n("0 to ∞ separated by -"),
                        value="0",
                        interactive=True,
                    )
                    gr.Textbox(
                        label=i18n("GPU Information"),
                        info=i18n("The GPU information will be displayed here."),
                        value=get_gpu_info(),
                        interactive=False,
                    )

        with gr.Row():
            train_output_info = gr.Textbox(
                label=i18n("Output Information"),
                info=i18n("The output information will be displayed here."),
                value="",
                max_lines=8,
                interactive=False,
            )

        with gr.Row():
            train_button = gr.Button(i18n("Start Training"))
            train_button.click(
                run_train_script,
                [
                    model_name,
                    rvc_version,
                    save_every_epoch,
                    save_only_latest,
                    save_every_weights,
                    total_epoch,
                    sampling_rate,
                    batch_size,
                    gpu,
                    pitch_guidance,
                    pretrained,
                    custom_pretrained,
                    g_pretrained_path,
                    d_pretrained_path,
                ],
                train_output_info,
                api_name="start_training",
            )

            index_button = gr.Button(i18n("Generate Index"))
            index_button.click(
                run_index_script,
                [model_name, rvc_version],
                train_output_info,
                api_name="generate_index",
            )

            def toggle_visible(checkbox):
                return {"visible": True, "__type__": "update"}

            refresh_datasets_button.click(
                fn=refresh_datasets,
                inputs=[],
                outputs=[dataset_path],
            )

            upload_audio_dataset.upload(
                fn=save_drop_dataset_audio,
                inputs=[upload_audio_dataset, dataset_name],
                outputs=[upload_audio_dataset, dataset_path],
            )

            custom_pretrained.change(
                fn=toggle_visible,
                inputs=[custom_pretrained],
                outputs=[pretrained_custom_settings],
            )

            refresh_custom_pretaineds_button.click(
                fn=refresh_custom_pretraineds,
                inputs=[],
                outputs=[g_pretrained_path, d_pretrained_path],
            )

            upload_pretrained.upload(
                fn=save_drop_model,
                inputs=[upload_pretrained],
                outputs=[upload_pretrained],
            )

            multiple_gpu.change(
                fn=toggle_visible,
                inputs=[multiple_gpu],
                outputs=[gpu_custom_settings],
            )
