import copy
import json
import sqlite3
import unittest
from app import bls_units

class BLSUnitsTests(unittest.TestCase):
    def entry(self):
        return {'id':'old','status':'processed','health_status':'pending','source':{'provider':'BLS'},'quantity':{'value':150,'unit':'g'},'food':{'bls_code':'X','nutrients':{'dietaryCholesterol':10,'dietaryVitaminB6':20,'dietaryCopper':30,'dietaryVitaminC':'TR','dietarySelenium':None,'dietaryWater':80}},'nutrients':{},'warnings':['Legacy BLS basis assumed per 100 g; confirm source units before Health export']}
    def test_pending_migration_units_unknowns_and_idempotency(self):
        e=self.entry()
        self.assertTrue(bls_units.upgrade(e))
        self.assertEqual(e['nutrients']['dietaryCholesterol'],{'value':15,'unit':'mg'})
        self.assertEqual(e['nutrients']['dietaryVitaminB6'],{'value':30,'unit':'mcg'})
        self.assertEqual(e['nutrients']['dietaryCopper'],{'value':45,'unit':'mcg'})
        self.assertNotIn('dietaryVitaminC',e['nutrients'])
        self.assertNotIn('dietarySelenium',e['nutrients'])
        self.assertNotIn('dietaryWater',bls_units.exportable(e))
        self.assertFalse(bls_units.blocked(e))
        snapshot=copy.deepcopy(e)
        self.assertFalse(bls_units.upgrade(e));self.assertEqual(e,snapshot)
    def test_exported_and_reserved_records_unchanged(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript('CREATE TABLE entries(id TEXT,payload TEXT);CREATE TABLE health_days(payload TEXT);')
        pending=self.entry();exported=self.entry();exported.update(id='exported',health_status='confirmed')
        reserved=self.entry();reserved['id']='reserved'
        for e in [pending,exported,reserved]:c.execute('INSERT INTO entries VALUES(?,?)',(e['id'],json.dumps(e)))
        c.execute('INSERT INTO health_days VALUES(?)',(json.dumps({'entry_ids':['reserved']}),))
        bls_units.migrate(c)
        results={row['id']:json.loads(row['payload']) for row in c.execute('SELECT * FROM entries')}
        self.assertEqual(results['exported'],exported);self.assertEqual(results['reserved'],reserved)
        self.assertFalse(bls_units.blocked(results['old']))
    def test_recipe_uses_frozen_ingredients_and_keeps_existing_totals(self):
        ingredient=self.entry()
        e={'id':'recipe','health_status':'pending','source':{'provider':'BLS'},'quantity':{'value':1,'unit':'portion'},'nutrients':{'dietaryProtein':{'value':99,'unit':'g'}},'recipe_snapshot':{'servings':2,'ingredients':[ingredient]}}
        self.assertTrue(bls_units.upgrade(e))
        self.assertEqual(e['nutrients']['dietaryCholesterol'],{'value':7.5,'unit':'mg'})
        self.assertEqual(e['nutrients']['dietaryProtein']['value'],99)
