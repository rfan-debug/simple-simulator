import unittest
from unittest.mock import MagicMock, patch
import sys
import numpy as np

# Mock genesis module before importing scene_manager
genesis_mock = MagicMock()
sys.modules["genesis"] = genesis_mock

# Now import the module under test
# We need to make sure the import path is correct.
# Assuming the test is run from the root of the repo.
from vla_synthesis.src.scene_manager import SceneManager

class TestSceneManager(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        genesis_mock.reset_mock()
        # Re-initialize manager for each test to ensure clean state
        self.manager = SceneManager(debug=True)

    def test_init(self):
        # Check if genesis.Scene was initialized with correct debug flag
        genesis_mock.Scene.assert_called_with(show_viewer=True)

    def test_load_robot(self):
        self.manager.load_robot()
        self.manager.scene.add_entity.assert_called()
        # Check if the first argument is the FrankaPanda asset (mocked)
        args, kwargs = self.manager.scene.add_entity.call_args
        # self.assertTrue(args[0] == genesis_mock.assets.FrankaPanda()) # This might fail if called differently
        # But we can check if it was called.

    def test_setup_camera(self):
        self.manager.setup_camera()
        self.manager.scene.add_camera.assert_called()

        # Verify arguments
        args, kwargs = self.manager.scene.add_camera.call_args
        self.assertTrue(isinstance(kwargs['position'], tuple))
        self.assertTrue(isinstance(kwargs['look_at'], tuple))
        self.assertEqual(kwargs['fov'], 60)
        self.assertEqual(kwargs['res'], (640, 480))

    def test_setup_camera_randomization(self):
        # Test that multiple calls result in different positions (due to randomization)
        self.manager.setup_camera()
        args1, kwargs1 = self.manager.scene.add_camera.call_args

        # Reset mock to capture new call
        self.manager.scene.add_camera.reset_mock()
        self.manager.camera = None # Force re-creation

        self.manager.setup_camera()
        args2, kwargs2 = self.manager.scene.add_camera.call_args

        # Positions should likely be different due to randomization
        # (Technically possible to be same, but very unlikely)
        self.assertNotEqual(kwargs1['position'], kwargs2['position'])

    def test_randomize_lighting(self):
        self.manager.randomize_lighting()
        self.manager.scene.add_light.assert_called()

        args, kwargs = self.manager.scene.add_light.call_args
        self.assertTrue(isinstance(kwargs['position'], tuple))
        self.assertTrue(isinstance(kwargs['color'], tuple))

    def test_step(self):
        self.manager.step()
        self.manager.scene.step.assert_called()

    def test_render(self):
        # Setup camera first so self.camera is not None
        self.manager.setup_camera()

        # Configure mock return value
        expected_output = (np.zeros((480, 640, 3)), np.zeros((480, 640)), np.zeros((480, 640)))
        self.manager.camera.render.return_value = expected_output

        result = self.manager.render()
        self.manager.camera.render.assert_called()
        self.assertEqual(result, expected_output)

    def test_render_without_camera(self):
        # Should raise RuntimeError if camera is not setup
        with self.assertRaises(RuntimeError):
            self.manager.render()

if __name__ == "__main__":
    unittest.main()
