import unittest
from PIL import Image
from rescuemind.corruptions import CONDITIONS, PARAMS, corrupt, corrupt_jpeg_bytes


class CorruptionTest(unittest.TestCase):
    def setUp(self):
        self.im = Image.new('RGB', (640, 480), (120, 130, 140))
        for x in range(200, 300):
            for y in range(200, 260):
                self.im.putpixel((x, y), (230, 60, 30))

    def test_registered_conditions(self):
        self.assertEqual(len(CONDITIONS), 12)
        self.assertEqual(set(PARAMS), {'gaussian_noise', 'motion_blur', 'defocus_blur', 'underexposure', 'overexposure', 'jpeg'})

    def test_deterministic_and_same_size(self):
        for c in CONDITIONS:
            a, b = corrupt(self.im, c, seed=3), corrupt(self.im, c, seed=3)
            self.assertEqual(a.size, (640, 480))
            self.assertEqual(a.tobytes(), b.tobytes(), c)

    def test_bytes_decodable(self):
        import io
        for c in CONDITIONS:
            self.assertEqual(Image.open(io.BytesIO(corrupt_jpeg_bytes(self.im, c, 1))).size, (640, 480))

    def test_exposure_direction(self):
        mean = lambda im: sum(im.convert('L').getdata()) / (640 * 480)
        self.assertLess(mean(corrupt(self.im, 'underexposure_S')), mean(self.im))
        self.assertGreater(mean(corrupt(self.im, 'overexposure_M')), mean(self.im))


if __name__ == '__main__':
    unittest.main()
