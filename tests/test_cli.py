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
        result = self.runner.invoke(cli, [])
        assert result.exit_code == 2
        assert "No command specified" in result.output
