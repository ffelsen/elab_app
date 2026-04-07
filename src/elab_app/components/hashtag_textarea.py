from pathlib import Path
import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "hashtag_textarea"

_hashtag_textarea_func = components.declare_component(
    "hashtag_textarea",
    path=str(_COMPONENT_DIR),
)


def hashtag_textarea(
    items: list,
    base_url: str,
    value: str = "",
    placeholder: str = "",
    reset_key: int = 0,
    key: str | None = None,
) -> dict | None:
    """Textarea with hashtag-triggered resource autocomplete.

    Parameters
    ----------
    items       : list of dicts with keys ``name``, ``id``, ``type``
    base_url    : elabFTW base URL, e.g. ``https://eln.ub.tum.de``
    value       : initial textarea content (applied only on first render)
    placeholder : placeholder text shown when textarea is empty
    key         : Streamlit component key

    Returns
    -------
    dict ``{text: str, submitted: bool}`` or ``None`` before first interaction.
    """
    return _hashtag_textarea_func(
        items=items,
        base_url=base_url,
        value=value,
        placeholder=placeholder,
        reset_key=reset_key,
        key=key,
        default=None,
    )
