import copy
import unittest
import numpy as np
import pandas as pd
from SRC.constants import PARTIES
from SRC.loaders import (load_seat_metadata,load_params,load_preference_matrices,load_partisan_vote_index,load_baseline_results_by_seat,load_baseline_primary_by_state)
from SRC.candidate_irv import load_candidate_irv_evidence
from SRC.forecast_engine import (run_forecast,count,fingerprint,government_events,perturb_local_primaries,uncertainty_profile)
from SRC.irv import apply_statewide_primary_adjustment
from SRC.forecast_params import defaults,load_forecast_params,parameter_table,validate
from SRC.forecast_preferences import perturb
from pathlib import Path
import tempfile

class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seats=load_seat_metadata();cls.params=load_params();cls.matrices=load_preference_matrices()
        cls.pvi=load_partisan_vote_index(cls.params);cls.baseline=load_baseline_results_by_seat()
        cls.national=load_baseline_primary_by_state();cls.evidence=load_candidate_irv_evidence()
        cls.targets=dict(zip(PARTIES,[34.56,31.82,12.2,6.4,7.27,7.75]))
    def run_model(self,settings):
        return run_forecast(self.seats,self.matrices,self.params,self.pvi,self.baseline,self.national,self.evidence,self.targets,settings)
    def test_zero_sd_parity_full_house(self):
        settings={k:0 if '_SD' in k else v for k,v in defaults().items()};settings['SIMULATIONS']=2
        adjusted=apply_statewide_primary_adjustment(self.seats,self.targets,self.pvi,params=self.params,baseline_results_by_seat=self.baseline,baseline_primary_by_state=self.national)
        result=count(adjusted,self.matrices,self.params,self.evidence)
        forecast=self.run_model(settings)
        self.assertEqual(forecast['winners'].iloc[0].tolist(),result.winner.tolist())
        np.testing.assert_allclose(forecast['seats']['Median ALP 2PP %'],result.ALP_2PP*100)
        np.testing.assert_allclose(forecast['seats']['Median winning margin pp'],(result.winner_pct-.5)*100)
        pd.testing.assert_frame_equal(perturb_local_primaries(adjusted,settings,np.random.default_rng(1)),adjusted)
    def test_reproduction_and_no_mutation(self):
        settings=defaults();settings['SIMULATIONS']=8
        original=fingerprint(self.seats,self.params,self.matrices,self.evidence)
        a=self.run_model(settings);b=self.run_model(settings)
        for key in ['winners','counts','seats','primaries']: pd.testing.assert_frame_equal(a[key],b[key])
        self.assertEqual(original,fingerprint(self.seats,self.params,self.matrices,self.evidence))
        self.assertTrue((a['counts'].sum(axis=1)==len(self.seats)).all())
        self.assertAlmostEqual(a['summary'].Average.sum(),len(self.seats))
        np.testing.assert_allclose(a['seats'][[p+' win %' for p in PARTIES]].sum(axis=1),100)
        self.assertNotEqual(fingerprint(settings),fingerprint({**settings,'SEED':3}))
    def test_local_balance_and_zeros(self):
        adjusted=apply_statewide_primary_adjustment(self.seats,self.targets,self.pvi,params=self.params,baseline_results_by_seat=self.baseline,baseline_primary_by_state=self.national)
        varied=perturb_local_primaries(adjusted,defaults(),np.random.default_rng(2))
        np.testing.assert_allclose(adjusted[PARTIES].sum(),varied[PARTIES].sum(),atol=1e-9)
        np.testing.assert_allclose(adjusted[PARTIES].sum(axis=1),varied[PARTIES].sum(axis=1),atol=1e-12)
        self.assertTrue((varied[PARTIES].to_numpy()[adjusted[PARTIES].to_numpy()==0]==0).all())
    def test_events_boundaries(self):
        counts=pd.DataFrame([[75,75,0,0,0,0],[74,40,1,35,0,0],[74,38,1,37,0,0],[70,38,4,38,0,0],[70,35,6,35,4,0]],columns=PARTIES)
        events=government_events(counts,150)
        self.assertTrue(events['Hung parliament'].iloc[0]);self.assertTrue(events['LNP + ON arithmetic (tied leadership)'].iloc[3])
        self.assertTrue(events['ALP + GRN or IND arithmetic (ALP below majority)'].iloc[4])
        self.assertFalse(events['Any party majority'].iloc[0])
    def test_strict_settings(self):
        for override in [{'SIMULATIONS':1.2},{'SEED':float('nan')},{'UNKNOWN':1},{'NATIONAL_SD_ON_PP':16}]:
            with self.assertRaises(ValueError): validate(override)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'params.csv';table=parameter_table();table=table.iloc[:-1];table.to_csv(path,index=False)
            with self.assertRaises(ValueError):load_forecast_params(path)
        profile=uncertainty_profile(defaults(),.5)
        self.assertEqual(profile['SEED'],defaults()['SEED']);self.assertEqual(profile['NATIONAL_SD_ON_PP'],1.5)
    def test_preference_source_and_zeros(self):
        shocks={'settings':defaults(),'origin':{p:{q:float(i) for i,q in enumerate(PARTIES)} for p in PARTIES},'class_on':{'Rural':1}}
        params={'_forecast_shocks':shocks};weights={'ALP':.5,'LNP':.5,'ON':0}
        a=perturb(weights,'IND','exact_candidate_transfer','Rural',params)
        b=perturb(weights,'IND','projected_candidate_transfer','Rural',params)
        self.assertEqual(a['ON'],0);self.assertAlmostEqual(sum(a.values()),1);self.assertNotEqual(a,b)
        self.assertEqual(perturb(weights,'IND','aec','Rural',{}),weights)

if __name__=='__main__':unittest.main()
