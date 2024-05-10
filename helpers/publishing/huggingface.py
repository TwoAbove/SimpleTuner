import os
from pathlib import Path
from helpers.training.state_tracker import StateTracker
from helpers.legacy.metadata import save_model_card

from huggingface_hub import create_repo, upload_folder, upload_file


class HubManager:
    def __init__(self, config, repo_id: str = None):
        self.config = config
        self.repo_id = (
            repo_id or self.config.hub_model_id or self.config.tracker_project_name
        )
        self.hub_token = self._load_hub_token()
        self.data_backends = StateTracker.get_data_backends()
        self._create_repo()
        self.validation_prompts = None
        self.collected_data_backend_str = None

    def _create_repo(self):
        self._repo_id = create_repo(
            repo_id=self.config.hub_model_id or self.config.tracker_project_name,
            exist_ok=True,
            token=self.config.hub_token,
        ).repo_id

    def _vae_string(self):
        if "deepfloyd" in self.config.model_type:
            return "\nDeepFloyd Pixel diffusion (no VAE)."
        else:
            return f"\nVAE: {self.config.pretrained_vae_model_name_or_path}"

    def _commit_message(self):
        return (
            f"Trained for {self.config.num_train_epochs} epochs and {StateTracker.get_global_step()} steps."
            f"\nTrained with datasets {self.collected_data_backend_str}"
            f"\nLearning rate {self.config.learning_rate}, batch size {self.config.train_batch_size}, and {self.config.gradient_accumulation_steps} gradient accumulation steps."
            f"\nUsed DDPM noise scheduler for training with {self.config.prediction_type} prediction type and rescaled_betas_zero_snr={self.config.rescale_betas_zero_snr}"
            f"\nUsing '{self.config.training_scheduler_timestep_spacing}' timestep spacing."
            f"\nBase model: {self.config.pretrained_model_name_or_path}"
            f"{self._vae_string()}"
        )

    def _load_hub_token(self):
        token_path = os.path.join(os.path.expanduser("~"), ".cache/huggingface/token")
        if os.path.exists(token_path):
            with open(token_path, "r") as f:
                return f.read().strip()
        raise ValueError(
            "No Hugging Face Hub token found. Please ensure you have logged in with 'huggingface-cli login'."
        )

    def set_validation_prompts(self, validation_prompts):
        self.validation_prompts = validation_prompts

    def upload_model(self, validation_images, webhook_handler=None):
        if webhook_handler:
            webhook_handler.send(
                message=f"Uploading model to Hugging Face Hub as `{self.repo_id}`."
            )
        save_model_card(
            repo_id=self.repo_id,
            images=validation_images,
            base_model=self.config.pretrained_model_name_or_path,
            train_text_encoder=self.config.train_text_encoder,
            prompt=self.config.validation_prompt,
            validation_prompts=self.validation_prompts,
            repo_folder=os.path.join(
                self.config.output_dir,
                "pipeline" if "lora" not in self.config.model_type else "",
            ),
        )
        self.upload_validation_images(validation_images, webhook_handler=None)
        attempt = 0
        while attempt < 3:
            attempt += 1
            try:
                if "lora" not in self.config.model_type:
                    self.upload_full_model()
                else:
                    self.upload_lora_model()
                break
            except Exception as e:
                if webhook_handler:
                    webhook_handler.send(
                        message=f"(attempt {attempt}/3) Error uploading model to Hugging Face Hub: {e}. Retrying..."
                    )
        if webhook_handler:
            webhook_handler.send(
                message=f"Model is now available [on Hugging Face Hub](https://huggingface.co/{self._repo_id})."
            )

    def upload_full_model(self):
        folder_path = os.path.join(self.config.output_dir, "pipeline")
        upload_folder(repo_id=self._repo_id, folder_path=folder_path)

    def upload_lora_model(self):
        lora_weights_path = os.path.join(
            self.config.output_dir, "pytorch_lora_weights.safetensors"
        )
        readme_path = os.path.join(self.config.output_dir, "README.md")
        upload_file(
            repo_id=self._repo_id,
            path_in_repo="/pytorch_lora_weights.safetensors",
            path_or_fileobj=lora_weights_path,
            commit_message=self._commit_message(),
        )
        upload_file(
            repo_id=self._repo_id,
            path_in_repo="/README.md",
            path_or_fileobj=readme_path,
            commit_message="Model card auto-generated by SimpleTuner",
        )

    def upload_validation_images(self, validation_images, webhook_handler=None):
        if validation_images and len(validation_images) > 0:
            for idx, image in enumerate(validation_images):
                image_path = os.path.join(
                    self.config.output_dir, "assets", f"image_{idx}.png"
                )
                attempt = 0
                while attempt < 3:
                    attempt += 1
                    try:
                        upload_file(
                            repo_id=self._repo_id,
                            path_in_repo=f"/assets/image_{idx}.png",
                            path_or_fileobj=image_path,
                            commit_message="Validation image auto-generated by SimpleTuner",
                        )
                    except Exception as e:
                        if webhook_handler:
                            webhook_handler.send(
                                message=f"(attempt {attempt}/3) Error uploading validation image to Hugging Face Hub: {e}. Retrying..."
                            )


# Example Usage:
# hub_manager.upload_model(args, validation_images, webhook_handler)
# hub_manager.upload_validation_images(repo_id, validation_images, args.output_dir)
