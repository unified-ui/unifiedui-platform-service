from abc import ABC, abstractmethod

from unifiedui.utils.dataclasses import to_dict


@to_dict
class BaseApplicationConfig:
    type: str = "NotSpecified"
