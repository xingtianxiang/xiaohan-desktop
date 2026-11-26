from pathlib import Path
import unittest
from PIL import Image, ImageChops
from animation import FRAME_COUNTS, frame_names
from outdoor import OutdoorRenderer

ASSETS=Path(__file__).resolve().parents[1]/'assets'


class OutdoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images={p.stem:Image.open(p).convert('RGBA') for p in ASSETS.glob('*.png')}
        cls.renderer=OutdoorRenderer(cls.images)

    def test_soft_edges_are_preserved_without_background_noise(self):
        sprite=self.renderer.sprite('park','red_puppy_walk0',122,False)
        alpha=sprite.getchannel('A')
        self.assertEqual(alpha.getpixel((0,0)),0)
        self.assertTrue(any(0<a<255 for a in alpha.getdata()))
        self.assertGreater(sum(a>240 for a in alpha.getdata()),1000)

    def test_ground_shadow_and_background_are_composited(self):
        background=self.renderer.backgrounds['park'].convert('RGB')
        frame=self.renderer.compose('park','blue_walk0',174,210,246)
        self.assertEqual(frame.mode,'RGB')
        self.assertEqual(frame.size,(420,290))
        self.assertEqual(frame.getpixel((5,5)),background.getpixel((5,5)))
        # The pet ends at ground=246; changes below it must be contact lighting.
        difference=ImageChops.difference(frame,background)
        self.assertIsNotNone(difference.crop((120,247,300,258)).getbbox())

    def test_scene_lighting_is_distinct(self):
        park=self.renderer.sprite('park','blue_walk0',174,False)
        snow=self.renderer.sprite('snow','blue_walk0',174,False)
        self.assertNotEqual(park.tobytes(),snow.tobytes())
        self.assertEqual(park.getchannel('A').tobytes(),snow.getchannel('A').tobytes())

    def test_all_ages_outfits_and_motions_fit_both_scenes(self):
        for scene in ('park','snow'):
            for outfit in ('blue','red','yellow'):
                for stage in range(3):
                    size=round(174*(.70,.88,1)[stage])
                    for motion in FRAME_COUNTS:
                        for name in frame_names(outfit,stage,motion):
                            for flip,x in ((False,118),(True,302)):
                                frame=self.renderer.compose(scene,name,size,x,246,flip)
                                diff=ImageChops.difference(frame,self.renderer.backgrounds[scene].convert('RGB'))
                                box=diff.getbbox()
                                self.assertIsNotNone(box,(scene,name))
                                self.assertGreater(box[0],0,(scene,name))
                                self.assertLess(box[2],420,(scene,name))
                                self.assertGreater(box[1],0,(scene,name))
                                self.assertLess(box[3],290,(scene,name))


if __name__=='__main__':unittest.main()
