import os
import sys
import logging
import gradio as gr
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from PIL import Image  # Import necessário para verificar o tamanho das imagens
import modules.scripts as scripts
from modules import script_callbacks



# Set the mode to DEBUG for detailed logging
#MODE = logging.DEBUG
MODE = logging.INFO

# Logger configuration
logger = logging.getLogger("GIFMovieMaker")
logger.propagate = False


loaded_count = 0


LOG_COLORS = {
    "DEBUG": "\033[0;34m",  # BLUE
    "INFO": "\033[0;32m",  # GREEN
    "WARNING": "\033[0;33m",  # YELLOW
    "ERROR": "\033[0;31m",  # RED
    "CRITICAL": "\033[1;31m",  # BOLD RED
    # ...other levels can be added here...
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log messages."""
    def format(self, record):
        log_color = LOG_COLORS.get(record.levelname, "")
        reset_color = "\033[0m"
        record.msg = f"{log_color}{record.msg}{reset_color}"
        return super().format(record)

def init_logger():
    """Initializes the logger to display messages in the console."""
    if not logger.handlers:
        logger.setLevel(MODE)  # Alterado para DEBUG para capturar logs de depuração
        handler = logging.StreamHandler(sys.stdout)
        formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

init_logger()

def make_animation(folder_path, fps, output_format, codec, audio_file=None):
    """Generates an animation (GIF or MP4) from a sequence of images."""
    
    # Check if folder_path is provided
    if not folder_path or not folder_path.strip():
        logger.error("The folder path is empty. Please provide a valid folder path.")
        return "Error: The folder path is empty."

    # Check if output_format is provided
    if not output_format or not output_format.strip():
        logger.error("The output format is empty. Please select a valid output format.")
        return "Error: The output format is empty."

    # Check if audio_file is provided when audio is expected
    if output_format == 'mp4' and audio_file and not audio_file.strip():
        logger.error("The audio file path is empty. Please provide a valid audio file path.")
        return "Error: The audio file path is empty."

    images = sorted([
        os.path.join(folder_path, img)
        for img in os.listdir(folder_path)
        if img.lower().endswith((".png", ".jpg", ".jpeg"))
    ])

    if not images:
        logger.error("No images found in the specified folder.")
        return "Error: No images found in the specified folder."
    
    logger.info(f"Found {len(images)} images. Creating {output_format.upper()} at {fps} FPS.")

    # Verificar se todas as imagens têm o mesmo tamanho
    logger.info("Checking image dimensions...")
    first_image_size = None
    for img_path in images:
        try:
            with Image.open(img_path) as img:
                if first_image_size is None:
                    first_image_size = img.size
                elif img.size != first_image_size:
                    logger.error(f"Image size mismatch: {img_path} has size {img.size}, expected {first_image_size}.")
                    return f"Error: Image size mismatch in {img_path}. All images must be the same size."
        except Exception as e:
            logger.error(f"Failed to open image {img_path}: {e}")
            return f"Error: Failed to open image {img_path}."

    logger.info(f"All images have the same size: {first_image_size}.")

    

    imageClip = ImageSequenceClip(images, fps=fps)

    output_dir = os.path.join(folder_path, "output")
    os.makedirs(output_dir, exist_ok=True)

    # Handle existing file names
    base_output_path = os.path.join(output_dir, f"output.{output_format}")
    output_path = base_output_path
    counter = 1
    while os.path.exists(output_path):
        output_path = os.path.join(output_dir, f"output_{counter}.{output_format}")
        counter += 1

    if output_format == 'gif':
        logger.info(f"Creating GIF at {fps} FPS.")
        imageClip.write_gif(output_path, fps=fps)
    else:
        if audio_file:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}")
                return "Audio file not found."
            
            try:
                logger.info(f"Adding audio from {audio_file}")
                audio_clip = AudioFileClip(audio_file)
            except Exception as e:
                logger.error(f"Failed to load audio file: {e}")
                return f"Failed to load audio file: {e}"
            
            # Verificar duração do áudio e do vídeo
            video_duration = imageClip.duration
            audio_duration = audio_clip.duration
            logger.info(f"Video duration: {video_duration}s, Audio duration: {audio_duration}s")

            imageClip.audio = audio_clip

            # Ajustar o áudio ao tamanho do vídeo, se necessário
            if audio_duration > video_duration:
                logger.info("Trimming audio to match video duration.")
                audio_clip = audio_clip.with_duration(video_duration)
                logger.info(f"Trimmed audio duration: {audio_clip.duration}s")

            imageClip = imageClip.with_audio(audio_clip)

        logger.info("Starting video processing...")
        try:
            ffmpeg_params = ["-pix_fmt", "yuv420p", "-bf", "0"]
            
            # Ajustar parâmetros com base no codec
            if codec == "h264_nvenc":
                ffmpeg_params.extend(["-profile:v", "main", "-cq", "22"])
            elif codec == "libx264":
                ffmpeg_params.extend(["-profile:v", "main", "-crf", "23"])
            elif codec == "mpeg4":
                ffmpeg_params.extend(["-qscale:v", "5"])  # Parâmetro específico para mpeg4

            imageClip.write_videofile(output_path, codec=codec, preset="fast", ffmpeg_params=ffmpeg_params)
        except OSError as e:
            logger.error(f"Failed to process video with codec {codec}: {e}")
            return f"Error: Failed to process video with codec {codec}."
        
        # Fechar o áudio apenas se ele foi carregado
        if audio_file:
            audio_clip.close()
        imageClip.close()

    logger.info(f"{output_format.upper()} successfully created at {output_path}")
    return output_path




def create_ui():
    """Creates the user interface for the GIF/MP4 generator."""
    with gr.Blocks() as ui:
        gr.Markdown("## GIF/MP4 Generator with MoviePy")
        with gr.Row():
            with gr.Column(scale=1):
                folder_input = gr.Textbox(
                    label="Folder with Images",
                    placeholder="C:/path/to/images",
                    elem_id="folder-input"
                )
                fps_input = gr.Slider(
                    minimum=1, 
                    maximum=60, 
                    value=8, 
                    step=1.0, 
                    label="FPS (Frames per Second)",
                    elem_id="fps-slider"
                )
                with gr.Row():
                    format_selector = gr.Dropdown(
                        choices=["mp4", "gif"], 
                        value="mp4", 
                        label="Output Format",
                        elem_id="format-selector"
                    )
                    codec_selector = gr.Dropdown(
                        choices=["h264_nvenc", "libx264", "mpeg4"], 
                        value="h264_nvenc", 
                        label="Codec (for MP4) - See Help for details",
                        visible=True,
                        elem_id="codec-selector"
                    )
                audio_input = gr.Checkbox(
                    label="Add Audio", 
                    value=False, 
                    visible=True,
                    elem_id="audio-checkbox"
                )
                audio_file_input = gr.Textbox(
                    label="Audio File Path", 
                    placeholder="C:/path/to/audio.mp3", 
                    visible=False,
                    elem_id="audio-file-input"
                )
            with gr.Column(scale=1):
                output_text = gr.Textbox(
                    label="Output Path", 
                    interactive=False, 
                    elem_id="output-path",
                    placeholder="Output path will be shown here"
                )
                btn = gr.Button(
                    "Generate Animation", 
                    elem_id="generate-button",
                )
                with gr.Accordion("Help", open=False):
                    gr.Markdown("""
                    ### Instructions
                    1. Select a folder with images.
                    2. Choose FPS and output format.
                    3. Optionally, add audio for MP4.
                    4. Click 'Generate Animation'.

                    ### Codec Information
                    - **h264_nvenc**: Uses NVIDIA GPU hardware acceleration for faster encoding. Requires a compatible GPU.
                    - **libx264**: A widely supported software-based codec. Slower but works on most systems.
                    - **mpeg4**: An older codec with broader compatibility but lower efficiency compared to h264.
                    """)
        
        # Atualizar visibilidade do codec_selector ao mudar o formato
        format_selector.change(
            lambda x: gr.update(visible=x == "mp4"),
            inputs=[format_selector],
            outputs=[codec_selector]
        )

        # Atualizar visibilidade da checkbox e do campo de áudio ao mudar o formato
        format_selector.change(
            lambda x: (
                gr.update(visible=x == "mp4"),  # Mostrar checkbox apenas para mp4
                gr.update(visible=x == "mp4" and audio_input.value)  # Mostrar caminho do áudio se checkbox estiver marcada
            ),
            inputs=[format_selector],
            outputs=[audio_input, audio_file_input]
        )

        # Atualizar visibilidade do campo de áudio ao marcar/desmarcar a checkbox
        audio_input.change(
            lambda x: gr.update(visible=x),
            inputs=[audio_input],
            outputs=[audio_file_input]
        )

        # Garantir que o campo de áudio reapareça ao trocar de gif para mp4 se a checkbox estiver marcada
        format_selector.change(
            lambda x: gr.update(value=False) if x == "gif" else gr.update(),
            inputs=[format_selector],
            outputs=[audio_input]
        )

        btn.click(make_animation, inputs=[folder_input, fps_input, format_selector, codec_selector, audio_file_input], outputs=output_text)

    return [(ui, "GIF/MP4 Maker", "gif_movie_maker_tab")]

# Register the tab in the UI
def on_ui_tabs():
    return create_ui()

def initialize():
    script_callbacks.on_ui_tabs(on_ui_tabs)  # Register the tab callback


class GifMovieMakerScript(scripts.Script):
    """Class for integrating with the Stable Diffusion script system."""
    
    def __init__(self):
        global loaded_count
        loaded_count += 1
        logger.debug("Initializing GIF/MP4 Maker tab.")
        logger.debug(f"Loaded count: {loaded_count}")
        if(loaded_count % 2 == 0):
            logger.debug("This script is already loaded. Skipping initialization.")
            return
        initialize()

    def title(self):
        return "GIF Movie Maker"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img=False, is_inpainting=False):
        return None  # No additional UI for other tabs

    def run(self, p):
        pass  # Function not used

