from core.tiers import Tier, classify


class TestClassify:
    def test_text_file_is_tier_1(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("hello\n")
        assert classify(path) is Tier.TEXT
        assert Tier.TEXT == 1

    def test_binary_file_is_tier_2(self, tmp_path):
        path = tmp_path / "blob.bin"
        path.write_bytes(b"\x00\x01\x02data")
        assert classify(path) is Tier.BINARY
        assert Tier.BINARY == 2

    def test_oversized_file_is_tier_3(self, tmp_path):
        path = tmp_path / "big.txt"
        path.write_bytes(b"x" * 100)
        assert classify(path, size_threshold=50) is Tier.OVERSIZED
        assert Tier.OVERSIZED == 3

    def test_size_threshold_is_inclusive_below(self, tmp_path):
        path = tmp_path / "edge.txt"
        path.write_bytes(b"x" * 50)
        assert classify(path, size_threshold=50) is Tier.TEXT
