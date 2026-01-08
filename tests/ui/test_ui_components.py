import pytest
from jinja2 import Environment, FileSystemLoader
import os

# Test des macros UI
def test_button_macro_with_aria_label():
    """Test que le macro button supporte aria-label"""
    template_dir = os.path.join(os.path.dirname(__file__), '../../app/templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('macros/ui.html')

    # Tester le bouton avec aria-label
    button_html = template.module.button(
        label='Sauvegarder',
        aria_label='Sauvegarder les modifications'
    )
    assert 'aria-label="Sauvegarder les modifications"' in button_html
    assert 'Sauvegarder' in button_html


def test_icon_macro_renders():
    """Test que le macro icon se rend correctement"""
    template_dir = os.path.join(os.path.dirname(__file__), '../../app/templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('macros/ui.html')

    # Tester l'icône check
    icon_html = template.module.icon('check')
    assert 'svg' in icon_html
    assert 'viewBox="0 0 24 24"' in icon_html
    assert 'd="M5 13l4 4L19 7"' in icon_html


def test_input_macro_accessibility():
    """Test que le macro input a les bons attributs d'accessibilité"""
    template_dir = os.path.join(os.path.dirname(__file__), '../../app/templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('macros/ui.html')

    # Tester l'input avec label
    input_html = template.module.input(
        name='email',
        label='Adresse email',
        type='email',
        required=True
    )
    assert 'label for="email"' in input_html
    assert 'id="email"' in input_html
    assert 'name="email"' in input_html
    assert 'required' in input_html
    assert 'type="email"' in input_html