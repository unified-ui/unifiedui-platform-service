from unifiedui.utils.dataclasses import to_dict


@to_dict
class BaseChatAgentConfig:
    type: str = "NotSpecified"
