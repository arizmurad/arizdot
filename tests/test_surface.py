import unittest
from surface import Painter,WIDTH,HEIGHT
from pulse import State
from motion import Morph


class SurfaceTests(unittest.TestCase):
    def test_curves_have_real_partial_transparency(self):
        painter=Painter()
        for progress in (0,.5,1):
            image=painter.draw(State(),progress,0)
            alpha=set(image.getchannel('A').tobytes())
            self.assertIn(0,alpha)
            self.assertIn(255,alpha)
            self.assertGreater(len(alpha),20)
            self.assertEqual(image.size,(WIDTH,HEIGHT))

    def test_faster_close_does_not_jump_on_reversal(self):
        m=Morph(.28)
        m.aim(True,1)
        before=m.value(1.14)
        self.assertEqual(m.aim(False,1.14,.23),before)
        self.assertEqual(m.value(2),0)


if __name__=='__main__':unittest.main()
