import h5py
import numpy as np

class HDF5Recorder:
    def __init__(self, save_path):
        """
        Initialize the HDF5Recorder with a save path.
        """
        self.save_path = save_path
        self.file = h5py.File(save_path, 'a')

    def create_episode_group(self, episode_idx):
        """
        Create a group in the HDF5 file for the current episode.
        """
        group_name = f'episode_{episode_idx}'
        if group_name not in self.file:
            self.file.create_group(group_name)

    def save_step(self, episode_idx, observation, action, instruction, reward, state=None):
        """
        Save a single step of data to the HDF5 file.

        Args:
            episode_idx (int): The index of the current episode.
            observation (np.ndarray): The RGB image (stored as uint8).
            action (np.ndarray): The joint positions/velocities (stored as float32).
            instruction (str): The text string (stored as variable-length string).
            reward (float): The reward for the step.
            state (np.ndarray, optional): Robot end-effector pose (stored as float32).
        """
        group_name = f'episode_{episode_idx}'
        if group_name not in self.file:
            self.create_episode_group(episode_idx)

        grp = self.file[group_name]

        # Handle Observation
        if 'observations' not in grp:
            # Assumes observation is (H, W, 3) or similar
            grp.create_dataset(
                'observations',
                data=np.expand_dims(observation, axis=0),
                maxshape=(None, *observation.shape),
                compression='gzip',
                dtype='uint8',
                chunks=True
            )
        else:
            grp['observations'].resize((grp['observations'].shape[0] + 1), axis=0)
            grp['observations'][-1] = observation

        # Handle Action
        if 'actions' not in grp:
            grp.create_dataset(
                'actions',
                data=np.expand_dims(action, axis=0),
                maxshape=(None, *action.shape),
                dtype='float32',
                chunks=True
            )
        else:
            grp['actions'].resize((grp['actions'].shape[0] + 1), axis=0)
            grp['actions'][-1] = action

        # Handle Instruction
        if 'instructions' not in grp:
            dt = h5py.string_dtype(encoding='utf-8')
            grp.create_dataset(
                'instructions',
                data=np.array([instruction], dtype=dt),
                maxshape=(None,),
                dtype=dt,
                chunks=True
            )
        else:
            grp['instructions'].resize((grp['instructions'].shape[0] + 1), axis=0)
            grp['instructions'][-1] = instruction

        # Handle Reward
        if 'rewards' not in grp:
            grp.create_dataset(
                'rewards',
                data=np.array([reward], dtype='float32'),
                maxshape=(None,),
                dtype='float32',
                chunks=True
            )
        else:
            grp['rewards'].resize((grp['rewards'].shape[0] + 1), axis=0)
            grp['rewards'][-1] = reward

        # Handle State (Optional)
        if state is not None:
            if 'states' not in grp:
                grp.create_dataset(
                    'states',
                    data=np.expand_dims(state, axis=0),
                    maxshape=(None, *state.shape),
                    dtype='float32',
                    chunks=True
                )
            else:
                grp['states'].resize((grp['states'].shape[0] + 1), axis=0)
                grp['states'][-1] = state

    def close(self):
        """
        Close the HDF5 file.
        """
        try:
            self.file.close()
        except:
            pass

    def __del__(self):
        self.close()
