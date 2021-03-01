"""Simple interface for loading sensitive credentials.  Intended to easily shim in other key management systems."""
import abc
import os


class CredentialLoader(abc.ABC):
    @abc.abstractmethod
    def load_credentials(self) -> str:
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
        CredentialLoader that reads credentials from disk in plaintext.
        Not secure.  Designed for prototyping, not production.

        Args:
            fpath: full path to credentials on disk
        """
        super().__init__()
        self.fpath = fpath

    def load_credentials(self) -> str:
        if not os.path.exists(self.fpath):
            raise FileNotFoundError(f"Cannot find credentials file {self.fpath}")
        with open(self.fpath, "r") as fh:
            lines = fh.readlines()
            if len(lines) != 1:
                raise NotImplementedError(
                    f"Not sure how to interpret multiline credential file {self.fpath} " f"({len(lines)} lines)."
                )
            credentials = lines[0].rstrip("\n")
        return credentials
