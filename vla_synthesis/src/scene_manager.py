import genesis
import numpy as np

class SceneManager:
    def __init__(self, debug=False):
        """
        Initialize the Genesis scene.

        Args:
            debug (bool): If True, shows the viewer. Defaults to False (headless).
        """
        self.scene = genesis.Scene(show_viewer=debug)
        self.robot = None
        self.camera = None
        self.light = None

    def load_robot(self):
        """
        Load a Franka Panda robot from Genesis standard assets.
        Fix its base to (0, 0, 0).
        """
        # Load a Franka Panda robot from Genesis standard assets.
        self.robot = self.scene.add_entity(
            genesis.assets.FrankaPanda(),
            position=(0.0, 0.0, 0.0),
            fixed=True
        )

    def setup_camera(self):
        """
        Add a camera that looks at the workspace (approx coordinate 0.5, 0, 0).
        Implements domain randomization with small random perturbations
        to the camera position and angle.
        """
        # Base settings: Camera positioned to look at workspace
        base_pos = np.array([1.0, 0.0, 0.5])
        base_look_at = np.array([0.5, 0.0, 0.0])

        # Domain randomization: Add small random perturbations
        pos_perturbation = np.random.uniform(-0.05, 0.05, 3)
        look_at_perturbation = np.random.uniform(-0.02, 0.02, 3)

        final_pos = base_pos + pos_perturbation
        final_look_at = base_look_at + look_at_perturbation

        # Add or update camera
        if self.camera is None:
            self.camera = self.scene.add_camera(
                position=tuple(final_pos),
                look_at=tuple(final_look_at),
                fov=60,
                res=(640, 480)
            )
        else:
            self.camera.set_pose(position=tuple(final_pos), look_at=tuple(final_look_at))

    def randomize_lighting(self):
        """
        Randomize light position and intensity.
        """
        # Randomize position (somewhere above the workspace)
        light_pos = np.array([0.5, 0.0, 2.0]) + np.random.uniform(-0.5, 0.5, 3)

        # Randomize intensity
        intensity = np.random.uniform(0.8, 1.2)

        if self.light is None:
            self.light = self.scene.add_light(
                position=tuple(light_pos),
                intensity=intensity,
                color=(1.0, 1.0, 1.0)
            )
        else:
            self.light.set_position(tuple(light_pos))
            self.light.set_intensity(intensity)

    def step(self):
        """
        Advance the physics simulation.
        """
        self.scene.step()

    def render(self):
        """
        Render the scene from the camera's perspective.

        Returns:
            tuple: (rgb, depth, segmentation_mask)
        """
        if self.camera is None:
            raise RuntimeError("Camera not initialized. Call setup_camera() first.")

        # Return (rgb, depth, segmentation_mask)
        return self.camera.render()
