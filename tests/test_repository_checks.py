import tempfile
import unittest
from pathlib import Path

from scripts.check_knowledge import check_markdown_links


class DocumentationLinksTests(unittest.TestCase):
    def test_local_links_are_resolved_relative_to_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root/"docs"
            docs.mkdir()
            (root/"AGENTS.md").write_text("Guide")
            page = docs/"guide.md"
            page.write_text("[guide](../AGENTS.md#route)\n[source](https://example.com/page)\n[section](#section)\n")
            self.assertEqual(check_markdown_links(page), [])
            (root/"AGENTS.md").unlink()
            self.assertEqual(len(check_markdown_links(page)), 1)

    def test_example_markdown_inside_fences_is_not_a_real_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp)/"guide.md"
            page.write_text("```markdown\n[example](customer-file.md)\n```\n[real](missing.md)\n")
            errors = check_markdown_links(page)
            self.assertEqual(len(errors), 1)
            self.assertIn("missing.md", errors[0])


if __name__ == "__main__":
    unittest.main()
