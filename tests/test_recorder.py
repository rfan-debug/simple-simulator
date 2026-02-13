import os
import numpy as np
import h5py
import pytest
from src.recorder import HDF5Recorder

def test_hdf5_recorder(tmp_path):
    save_path = tmp_path / "test_data.h5"
    recorder = HDF5Recorder(str(save_path))

    episode_idx = 0
    recorder.create_episode_group(episode_idx)

    # Create dummy data
    obs = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    action = np.random.rand(7).astype(np.float32)
    instruction = "pick up the apple"
    reward = 1.0
    state = np.random.rand(6).astype(np.float32)

    # Save step
    recorder.save_step(episode_idx, obs, action, instruction, reward, state)

    # Save another step
    obs2 = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    action2 = np.random.rand(7).astype(np.float32)
    instruction2 = "pick up the apple 2"
    reward2 = 0.0
    state2 = np.random.rand(6).astype(np.float32)

    recorder.save_step(episode_idx, obs2, action2, instruction2, reward2, state2)

    recorder.close()

    # Verify data
    assert os.path.exists(save_path)

    with h5py.File(save_path, 'r') as f:
        assert f'episode_{episode_idx}' in f
        grp = f[f'episode_{episode_idx}']

        assert 'observations' in grp
        assert grp['observations'].shape == (2, 256, 256, 3)
        assert grp['observations'].dtype == 'uint8'
        assert grp['observations'].compression == 'gzip'
        np.testing.assert_array_equal(grp['observations'][0], obs)
        np.testing.assert_array_equal(grp['observations'][1], obs2)

        assert 'actions' in grp
        assert grp['actions'].shape == (2, 7)
        assert grp['actions'].dtype == 'float32'
        np.testing.assert_array_equal(grp['actions'][0], action)
        np.testing.assert_array_equal(grp['actions'][1], action2)

        assert 'instructions' in grp
        assert grp['instructions'].shape == (2,)
        assert grp['instructions'][0].decode('utf-8') == instruction
        assert grp['instructions'][1].decode('utf-8') == instruction2

        assert 'rewards' in grp
        assert grp['rewards'].shape == (2,)
        assert grp['rewards'][0] == reward
        assert grp['rewards'][1] == reward2

        assert 'states' in grp
        assert grp['states'].shape == (2, 6)
        assert grp['states'].dtype == 'float32'
        np.testing.assert_array_equal(grp['states'][0], state)
        np.testing.assert_array_equal(grp['states'][1], state2)

def test_hdf5_recorder_no_state(tmp_path):
    save_path = tmp_path / "test_data_no_state.h5"
    recorder = HDF5Recorder(str(save_path))

    episode_idx = 1
    # Implicit group creation via save_step

    obs = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    action = np.random.rand(4).astype(np.float32)
    instruction = "move forward"
    reward = 0.5

    recorder.save_step(episode_idx, obs, action, instruction, reward)

    recorder.close()

    with h5py.File(save_path, 'r') as f:
        grp = f[f'episode_{episode_idx}']
        assert 'states' not in grp
        assert grp['observations'].shape == (1, 64, 64, 3)
