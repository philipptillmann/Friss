"""BLS 4.0 source units, verified against the user's original 2025 workbook.

All source values are per 100 g. Legacy JSON retains these units unchanged.
Vitamin A / folate variants have the same source units; no variant substitution
or nutrient estimation is performed. Selenium and caffeine are absent from the
provided component catalogue, and deliberately have no inferred source unit.
"""
import json
import math

UNITS = {'dietary'+k:'g' for k in 'Carbohydrates Fiber Sugar FatTotal FatMonounsaturated FatPolyunsaturated FatSaturated Protein Water'.split()}
UNITS['dietaryEnergyConsumed']='kcal'
UNITS.update({'dietary'+k:'mg' for k in 'Cholesterol Thiamin Riboflavin Niacin PantothenicAcid VitaminC VitaminE Calcium Chloride Iron Magnesium Phosphorus Potassium Sodium Zinc'.split()})
UNITS.update({'dietary'+k:'mcg' for k in 'VitaminA VitaminB6 Biotin VitaminB12 VitaminD VitaminK Folate Chromium Copper Iodine Manganese Molybdenum'.split()})
VERSION='BLS-4.0-2025-source-units-v1'

def numeric(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0

def blocked(e):
    return e.get('source',{}).get('provider')=='BLS' and e.get('source',{}).get('units_version')!=VERSION

def upgrade(e):
    """Enrich only unexported entries using their own retained food snapshots.

    Existing recipe totals are kept; missing values are derived from the frozen
    ingredients, never the current recipe. Original files / Health batches are
    never rewritten. Trace and missing values stay unknown.
    """
    if e.get('health_status')!='pending' or not blocked(e):return False
    q=e.get('quantity') or {};food=e.get('food') or {};r=e.get('recipe_snapshot')
    if food.get('bls_code') and q.get('unit')=='g':
        for key,raw in food.get('nutrients',{}).items():
            if key in UNITS and numeric(raw):
                e.setdefault('nutrients',{})[key]={'value':raw*q['value']/100,'unit':UNITS[key]}
    elif r:
        for ingredient in r['ingredients']:upgrade(ingredient)
        # Every BLS component must have an auditable retained snapshot.
        if any(blocked(i) for i in r['ingredients']):return False
        sources=[i.get('nutrients',{}) for i in r['ingredients']]
        keys=set.intersection(*(set(v) for v in sources)) if sources else set()
        factor=q['value']/r['servings'] if q['unit']=='portion' else q['value']/r['finished_weight_g'] if q['unit']=='g' else q['value']
        mass={'g':1,'mg':.001,'mcg':.000001}
        for key in keys:
            if key in e.get('nutrients',{}):continue
            terms=[s[key] for s in sources];unit=terms[0]['unit']
            if all(v['unit']==unit for v in terms):total=sum(v['value'] for v in terms)
            elif unit in mass and all(v['unit'] in mass for v in terms):total=sum(v['value']*mass[v['unit']]/mass[unit] for v in terms)
            else:continue
            e.setdefault('nutrients',{})[key]={'value':total*factor,'unit':unit}
    else:return False
    e['source']['units_version']=VERSION
    e['warnings']=[w for w in e.get('warnings',[]) if not w.startswith('Legacy BLS basis assumed') and not any(w==k+': source value or unit unresolved' for k in e.get('nutrients',{}))]
    return True

def migrate(connection):
    reserved={eid for row in connection.execute('SELECT payload FROM health_days') for eid in json.loads(row['payload'])['entry_ids']}
    for row in connection.execute('SELECT id,payload FROM entries').fetchall():
        e=json.loads(row['payload'])
        if e['id'] not in reserved and upgrade(e):
            connection.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),e['id']))

def exportable(e):
    """Health water expects volume; retain source water mass only internally."""
    return {k:v for k,v in e.get('nutrients',{}).items() if k!='dietaryWater' or v.get('unit')=='ml'}
