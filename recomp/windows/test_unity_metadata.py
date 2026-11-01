"""Checked executable ranges include interior return PCs, not only trace heads."""
import copy
import unittest
from unity_bootstrap_prepare import executable_ranges


class ExecutableRanges(unittest.TestCase):
    def setUp(self):
        self.manifest={'base':0x70000000,'image_span':0x1400000,
                       'executable_ranges':[[0x700b8050,0x700b95f0],[0x700b95f0,0x70ebad80]]}

    def test_interior_return(self):
        ranges=executable_ranges(self.manifest)
        self.assertTrue(any(low<=0x7043a04c<high for low,high in ranges))
        self.assertFalse(any(low<=0x70000100<high for low,high in ranges))
        self.assertFalse(any(low<=0x70ebad80<high for low,high in ranges))

    def test_invalid_ranges(self):
        for ranges in ([],[[1,2]],[[0x700b8050,0x700b8050]],
                       [[0x700b8050,0x71400004]],[[0x700b8051,0x700b8058]],
                       [[0x700b8050,0x700b95f0],[0x700b95e0,0x700b9600]],
                       [[True,0x700b95f0]],[[0x700b8050]]):
            with self.subTest(ranges=ranges):
                manifest=copy.deepcopy(self.manifest);manifest['executable_ranges']=ranges
                with self.assertRaises(RuntimeError):executable_ranges(manifest)


if __name__=='__main__':unittest.main()
