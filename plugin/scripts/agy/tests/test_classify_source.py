import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from classify_source import classify

class TestClassify(unittest.TestCase):
    def wf(self, r):
        return r["write_file"].replace(os.getcwd() + os.sep, "").replace(os.getcwd(), "")
    def test_transcribe_video_ext(self):
        r = classify("transcribe", "reunion.mp4")
        self.assertEqual(r["kind"], "video")
        self.assertTrue(self.wf(r).endswith("docs/gemini/transcripts/reunion.md"))
    def test_transcribe_audio_default_and_slug(self):
        r = classify("transcribe", "note vocale.OGG")
        self.assertEqual(r["kind"], "audio")
        self.assertTrue(self.wf(r).endswith("docs/gemini/transcripts/note-vocale.md"))
    def test_transcribe_url(self):
        r = classify("transcribe", "https://youtu.be/AbC_123")
        self.assertEqual(r["kind"], "url")
        self.assertEqual(r["add_dir"], "")
        self.assertTrue(self.wf(r).endswith("docs/gemini/transcripts/youtu-be-abc-123.md"))
    def test_video_url(self):
        r = classify("video", "https://www.example.com/demo")
        self.assertEqual(r["kind"], "url")
        self.assertTrue(self.wf(r).endswith("docs/gemini/video/example-com-demo.md"))
    def test_media_video_with_question_hash(self):
        r = classify("media", "clip.MOV", "que decide-t-on a 2:30?")
        self.assertEqual(r["kind"], "video")
        self.assertRegex(self.wf(r), r"docs/gemini/media/clip-[0-9a-f]{6}\.md$")
    def test_media_image(self):
        r = classify("media", "photo.JPEG", "quoi?")
        self.assertEqual(r["kind"], "image")
    def test_doc_to_md_pdf_dated(self):
        r = classify("doc-to-md", "Contrat Final.PDF", today="2026-07-17")
        self.assertEqual(r["kind"], "pdf")
        self.assertTrue(self.wf(r).endswith("docs/gemini/converted/2026-07-17-contrat-final.md"))
    def test_doc_to_md_html_and_image_and_other(self):
        self.assertEqual(classify("doc-to-md", "page.HTM")["kind"], "html")
        self.assertEqual(classify("doc-to-md", "scan.png")["kind"], "image")
        self.assertEqual(classify("doc-to-md", "data.xyz")["kind"], "other")
    def test_file_add_dir_is_absolute(self):
        r = classify("transcribe", "reunion.mp4")
        self.assertTrue(os.path.isabs(r["add_dir"]))

if __name__ == "__main__":
    unittest.main()
