"""Tests for CLI module."""

import pytest
from click.testing import CliRunner
from src.cli.cli import cli


class TestCLI:
    """Test CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'UDSv4-NU' in result.output
    
    def test_cli_version(self):
        """Test CLI version command."""
        result = self.runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        from src.cli.cli import CLI_VERSION; assert CLI_VERSION in result.output
    
    def test_upload_validation(self):
        """Test that upload validates required fields."""
        # Missing both initials and adcid
        result = self.runner.invoke(cli, ['main-command', '--upload'])
        # Should fail with validation error
        assert result.exit_code != 0
