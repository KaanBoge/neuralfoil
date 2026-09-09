"""Mock Markdown only. Does not read either actual display source."""
import unittest
import prepare_presentation_blocks as p
def table(i):return f'| Label | Value |\n|---|---|\n| Case {i} | -0.00100 / 42 ({i}) |\n\n'
def fixture():
    paired=p.PAIRED_TOP+''.join(f'Table P{i}. Existing caption.\n\n'+table(i) for i in range(1,4))
    paired=paired.replace('Table P1. Existing caption.','Table P1. '+', '.join(old for old,new in p.PAIRED_SPACING)+'.')
    timing='# Literal-request timing displays\n\nAll times are milliseconds for complete497 rows at(n−1)q; Q25,Q75.\n\n'+''.join(old+'\n'+table(i) for i,(old,new) in enumerate(p.TIMING_CAPTIONS,1))+'Positive reduction means lower reuse median; negative means slower.'+p.TIMING_PROSE[-1][1]+'\n'
    return paired,timing
class Tests(unittest.TestCase):
    def test_exact_full_table_bytes_and_only_declared_text_changes(self):
        a,b=fixture();out,changes=p.transform(a,b)
        expected_paired=a[len(p.PAIRED_TOP):]
        for old,new in p.PAIRED_SPACING:expected_paired=expected_paired.replace(old,new,1)
        self.assertEqual(out['paired'],expected_paired);self.assertEqual(p.tables(a),p.tables(out['paired']));self.assertEqual(p.tables(b),p.tables(out['timing']))
        expected=b
        for scope,old,new in p.TIMING_PROSE:expected=expected.replace(old,new,1)
        for old,new in p.TIMING_CAPTIONS:expected=expected.replace(old,new,1)
        self.assertEqual(out['timing'],expected);self.assertEqual(len(changes),15)
        self.assertTrue(all(change['count']==1 for change in changes))
    def test_missing_duplicate_headings_fail(self):
        a,b=fixture()
        for changed in [b.replace('## V6\n',''),b+'## V6\n']:
            with self.assertRaises(ValueError):p.transform(a,changed)
        with self.assertRaises(ValueError):p.transform(a+p.PAIRED_TOP,b)
    def test_missing_table_and_caption_fail(self):
        a,b=fixture()
        with self.assertRaises(ValueError):p.transform(a.replace(table(2),''),b)
        with self.assertRaises(ValueError):p.transform(a.replace('Table P2.','Table P4.'),b)
    def test_spacing_strings_inside_table_are_untouched(self):
        a,b=fixture();a=a.replace('Case 1','Case all16 seed2026090831');b=b.replace('Case 1','Case Q25,Q75 complete497')
        out,_=p.transform(a,b)
        self.assertEqual(p.tables(a),p.tables(out['paired']));self.assertEqual(p.tables(b),p.tables(out['timing']))
    def test_missing_or_duplicate_scoped_prose_rejected(self):
        a,b=fixture()
        with self.assertRaises(ValueError):p.transform(a.replace('all16','all 16'),b)
        with self.assertRaises(ValueError):p.transform(a,b.replace('complete497','complete497 complete497'))
if __name__=='__main__':unittest.main()
