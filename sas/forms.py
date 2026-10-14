from django import forms


class BootstrapFormMixin:
    """Give every widget the Bootstrap class it needs so templates stay simple."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect,
                                   forms.CheckboxSelectMultiple)):
                continue
            css = 'custom-select' if isinstance(widget, forms.Select) else 'form-control'
            widget.attrs['class'] = (widget.attrs.get('class', '') + ' ' + css).strip()
