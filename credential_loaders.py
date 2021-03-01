"""Simple interface for loading sensitive credentials.  Intended to easily shim in other key management systems."""
import abc
import json
import os


class CredentialLoader(abc.ABC):
    @abc.abstractmethod
    def load_credentials(self):
        """Loads credentials per the child implementation (e.g. environment variable, local file, GCP-KMS...)"""
        pass


class EnvVarCredentialLoader(CredentialLoader):
    def __init__(self, env_var_name):
        """
        CredentialLoader that loads credential from environment variable.

        Args:
            env_var_name: Name of environment variable to load (e.g. 'MY_SECRET_PW')
        """
        super().__init__()
        self.env_var_name = env_var_name

    def load_credentials(self) -> str:
        if self.env_var_name not in os.environ:
            raise ValueError(f"{self.__class__.__name__} expected env var {self.env_var_name} to be set")
        return os.environ[self.env_var_name]


class PlaintextCredentialLoader(CredentialLoader):
    def __init__(self, fpath):
        """
        CredentialLoader that saves credentials to disk in JSON-formatted plaintext.
        This is the most straightforward (and least secure) CredentialLoader.
        It's useful for prototyping quickly, but ill-advised for production.

        Args:
            fpath: Name of credential (used for logging)
        """
        super().__init__()
        self.fpath = fpath

    def load_credentials(self) -> dict:
        if not os.path.exists(self.fpath):
            raise FileNotFoundError(f"Cannot find credentials file {self.fpath}")
        with open(self.fpath, "r") as fh:
            credential_dict = json.load(fh)
        return credential_dict
