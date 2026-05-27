import unittest

from agents import Model, ModelProvider, get_provider


class TestModelEnum(unittest.TestCase):
    """Test cases for the Model enum class."""

    def test_model_enum_inheritance(self):
        """Test that Model enum inherits from str and Enum."""
        self.assertTrue(issubclass(Model, str))
        self.assertTrue(hasattr(Model, "__members__"))

    def test_model_enum_values(self):
        """Test that all expected model values are present."""
        expected_models = {
            # OpenAI models
            "gpt_5_4": "gpt-5.4",
            "gpt_5_4_mini": "gpt-5.4-mini",
            "gpt_5_4_nano": "gpt-5.4-nano",
            # Gemini stable models
            "gemini_2_5_pro": "gemini-2.5-pro",
            "gemini_2_5_flash": "gemini-2.5-flash",
            "gemini_2_5_flash_lite": "gemini-2.5-flash-lite",
            # Gemini preview models
            "gemini_3_1_pro": "gemini-3.1-pro-preview",
            "gemini_3_flash": "gemini-3-flash-preview",
            # Anthropic models
            "claude_opus_4_6": "claude-opus-4-6",
            "claude_sonnet_4_6": "claude-sonnet-4-6",
            "claude_haiku_4_5": "claude-haiku-4-5-20251001",
        }

        for attr_name, expected_value in expected_models.items():
            with self.subTest(model=attr_name):
                self.assertTrue(hasattr(Model, attr_name))
                model = getattr(Model, attr_name)
                self.assertEqual(model.value, expected_value)
                self.assertEqual(model, expected_value)

    def test_model_enum_string_behavior(self):
        """Test that Model enum members behave like strings."""
        self.assertEqual(Model.gpt_5_4, "gpt-5.4")
        self.assertEqual(Model.gemini_2_5_pro, "gemini-2.5-pro")
        self.assertEqual(Model.claude_sonnet_4_6, "claude-sonnet-4-6")

        self.assertTrue(Model.gpt_5_4.startswith("gpt"))
        self.assertTrue(Model.gemini_2_5_pro.startswith("gemini"))
        self.assertTrue(Model.claude_sonnet_4_6.startswith("claude"))
        self.assertIn("flash", Model.gemini_2_5_flash)

        concatenated = Model.gpt_5_4 + "-test"
        self.assertEqual(concatenated, "gpt-5.4-test")

    def test_model_enum_membership(self):
        """Test enum membership and iteration."""
        all_models = list(Model)
        self.assertEqual(len(all_models), 11)

        expected_values = [
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ]

        enum_values = [model.value for model in Model]
        for expected_value in expected_values:
            self.assertIn(expected_value, enum_values)

    def test_model_enum_comparison(self):
        """Test comparison operations between Model enum members."""
        self.assertEqual(Model.gpt_5_4, Model.gpt_5_4)
        self.assertNotEqual(Model.gpt_5_4, Model.gpt_5_4_mini)
        self.assertIs(Model.gpt_5_4, Model.gpt_5_4)
        self.assertIsNot(Model.gpt_5_4, Model.gemini_2_5_pro)

    def test_model_enum_creation_from_string(self):
        """Test creating Model enum instances from string values."""
        model_from_string = Model("gpt-5.4")
        self.assertEqual(model_from_string, Model.gpt_5_4)

        gemini_from_string = Model("gemini-2.5-pro")
        self.assertEqual(gemini_from_string, Model.gemini_2_5_pro)

        claude_from_string = Model("claude-sonnet-4-6")
        self.assertEqual(claude_from_string, Model.claude_sonnet_4_6)

        with self.assertRaises(ValueError):
            Model("invalid-model")

        with self.assertRaises(ValueError):
            Model("gpt-4")

    def test_model_enum_in_collections(self):
        """Test using Model enum in collections."""
        model_list = [Model.gpt_5_4, Model.gemini_2_5_pro]
        self.assertIn(Model.gpt_5_4, model_list)
        self.assertNotIn(Model.gpt_5_4_mini, model_list)

        model_set = {Model.gpt_5_4, Model.gemini_2_5_flash}
        self.assertIn(Model.gpt_5_4, model_set)
        self.assertEqual(len(model_set), 2)

        model_dict = {
            Model.gpt_5_4: "OpenAI GPT-5.4",
            Model.gemini_2_5_pro: "Google Gemini 2.5 Pro",
            Model.claude_sonnet_4_6: "Anthropic Claude Sonnet 4.6",
        }
        self.assertEqual(model_dict[Model.gpt_5_4], "OpenAI GPT-5.4")
        self.assertEqual(model_dict[Model.gemini_2_5_pro], "Google Gemini 2.5 Pro")
        self.assertEqual(model_dict[Model.claude_sonnet_4_6], "Anthropic Claude Sonnet 4.6")

    def test_model_enum_serialization(self):
        """Test JSON serialization behavior."""
        import json

        model_data = {
            "model": Model.gpt_5_4,
            "backup_model": Model.gemini_2_5_pro,
            "claude_model": Model.claude_sonnet_4_6,
        }

        json_str = json.dumps(model_data)
        self.assertIn('"gpt-5.4"', json_str)
        self.assertIn('"gemini-2.5-pro"', json_str)
        self.assertIn('"claude-sonnet-4-6"', json_str)

    def test_openai_models_group(self):
        """Test OpenAI GPT model variants."""
        gpt_models = [Model.gpt_5_4, Model.gpt_5_4_mini, Model.gpt_5_4_nano]

        for model in gpt_models:
            with self.subTest(model=model):
                self.assertTrue(model.startswith("gpt-"))

        self.assertEqual(Model.gpt_5_4, "gpt-5.4")
        self.assertEqual(Model.gpt_5_4_mini, "gpt-5.4-mini")
        self.assertEqual(Model.gpt_5_4_nano, "gpt-5.4-nano")

    def test_gemini_models_group(self):
        """Test Gemini model variants."""
        gemini_models = [
            Model.gemini_2_5_pro,
            Model.gemini_2_5_flash,
            Model.gemini_2_5_flash_lite,
            Model.gemini_3_1_pro,
            Model.gemini_3_flash,
        ]

        for model in gemini_models:
            with self.subTest(model=model):
                self.assertTrue(model.startswith("gemini-"))

        self.assertEqual(Model.gemini_2_5_pro, "gemini-2.5-pro")
        self.assertEqual(Model.gemini_2_5_flash, "gemini-2.5-flash")
        self.assertEqual(Model.gemini_2_5_flash_lite, "gemini-2.5-flash-lite")
        self.assertEqual(Model.gemini_3_1_pro, "gemini-3.1-pro-preview")
        self.assertEqual(Model.gemini_3_flash, "gemini-3-flash-preview")

    def test_anthropic_models_group(self):
        """Test Anthropic Claude model variants."""
        claude_models = [Model.claude_opus_4_6, Model.claude_sonnet_4_6, Model.claude_haiku_4_5]

        for model in claude_models:
            with self.subTest(model=model):
                self.assertTrue(model.startswith("claude-"))

        self.assertEqual(Model.claude_opus_4_6, "claude-opus-4-6")
        self.assertEqual(Model.claude_sonnet_4_6, "claude-sonnet-4-6")
        self.assertEqual(Model.claude_haiku_4_5, "claude-haiku-4-5-20251001")

    def test_model_enum_repr(self):
        """Test string representation of Model enum members."""
        self.assertEqual(repr(Model.gpt_5_4), "<Model.gpt_5_4: 'gpt-5.4'>")
        self.assertEqual(repr(Model.gemini_2_5_pro), "<Model.gemini_2_5_pro: 'gemini-2.5-pro'>")
        self.assertEqual(repr(Model.claude_sonnet_4_6), "<Model.claude_sonnet_4_6: 'claude-sonnet-4-6'>")

    def test_model_enum_name_and_value_attributes(self):
        """Test name and value attributes of Model enum members."""
        self.assertEqual(Model.gpt_5_4.name, "gpt_5_4")
        self.assertEqual(Model.gpt_5_4.value, "gpt-5.4")

        self.assertEqual(Model.gemini_2_5_flash.name, "gemini_2_5_flash")
        self.assertEqual(Model.gemini_2_5_flash.value, "gemini-2.5-flash")

        self.assertEqual(Model.claude_sonnet_4_6.name, "claude_sonnet_4_6")
        self.assertEqual(Model.claude_sonnet_4_6.value, "claude-sonnet-4-6")

    def test_model_enum_uniqueness(self):
        """Test that all enum members are unique."""
        model_values = [model.value for model in Model]
        model_names = [model.name for model in Model]

        self.assertEqual(len(model_values), len(set(model_values)))
        self.assertEqual(len(model_names), len(set(model_names)))

    def test_model_provider_enum(self):
        """Test ModelProvider enum."""
        self.assertEqual(ModelProvider.OPENAI.value, "openai")
        self.assertEqual(ModelProvider.GEMINI.value, "gemini")
        self.assertEqual(ModelProvider.ANTHROPIC.value, "anthropic")

        all_providers = list(ModelProvider)
        self.assertEqual(len(all_providers), 3)

    def test_get_provider_function(self):
        """Test get_provider() returns correct provider for each model."""
        # OpenAI GPT models
        self.assertEqual(get_provider(Model.gpt_5_4), ModelProvider.OPENAI)
        self.assertEqual(get_provider(Model.gpt_5_4_mini), ModelProvider.OPENAI)
        self.assertEqual(get_provider(Model.gpt_5_4_nano), ModelProvider.OPENAI)

        # Gemini models
        self.assertEqual(get_provider(Model.gemini_2_5_pro), ModelProvider.GEMINI)
        self.assertEqual(get_provider(Model.gemini_2_5_flash), ModelProvider.GEMINI)
        self.assertEqual(get_provider(Model.gemini_2_5_flash_lite), ModelProvider.GEMINI)
        self.assertEqual(get_provider(Model.gemini_3_1_pro), ModelProvider.GEMINI)
        self.assertEqual(get_provider(Model.gemini_3_flash), ModelProvider.GEMINI)

        # Anthropic models
        self.assertEqual(get_provider(Model.claude_opus_4_6), ModelProvider.ANTHROPIC)
        self.assertEqual(get_provider(Model.claude_sonnet_4_6), ModelProvider.ANTHROPIC)
        self.assertEqual(get_provider(Model.claude_haiku_4_5), ModelProvider.ANTHROPIC)


if __name__ == "__main__":
    unittest.main()
