import inspect

import pytest

from tls_client import Session
from tls_client.settings import CLIENT_IDENTIFIERS


class TestValidation:
    @pytest.mark.parametrize("identifier", CLIENT_IDENTIFIERS)
    def test_every_listed_identifier_is_accepted(self, identifier):
        assert Session(client_identifier=identifier).client_identifier == identifier

    def test_default_identifier_is_listed(self):
        default = inspect.signature(Session).parameters["client_identifier"].default

        assert default in CLIENT_IDENTIFIERS

    def test_none_selects_a_custom_tls_configuration(self):
        assert Session(client_identifier=None, ja3_string="771,4865,0,29,0").client_identifier is None

    @pytest.mark.parametrize(
        ("identifier", "suggestion"),
        [
            # The typos that used to be in the README.
            ("chrome109", "chrome_109"),
            ("Chrome110", "chrome_110"),
            ("firefox108", "firefox_108"),
            ("Firefox110", "firefox_110"),
            ("CHROME_120", "chrome_120"),
            ("chrome_116_psk", "chrome_116_PSK"),
        ],
    )
    def test_unknown_identifier_is_rejected_with_close_matches(self, identifier, suggestion):
        with pytest.raises(ValueError, match=f"Unknown client_identifier '{identifier}'") as rejected:
            Session(client_identifier=identifier)

        assert f"'{suggestion}'" in str(rejected.value)

    def test_unknown_identifier_without_close_matches_points_to_the_full_list(self):
        with pytest.raises(ValueError, match="Unknown client_identifier 'edge_120'") as rejected:
            Session(client_identifier="edge_120")

        assert "Did you mean" not in str(rejected.value)
        assert "tls_client/settings.py" in str(rejected.value)
