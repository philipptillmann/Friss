"""Reversible, opt-in interpretation of blank nutrient values as zero.

Source payloads are never changed. The opt-in includes trace / detection-limit
qualifiers. Unknown food identities, amounts and unverified numeric units remain.
"""
import json
import re
from .bls_units import UNITS

ZERO_UNITS={**UNITS,'dietarySelenium':'mcg','dietaryCaffeine':'mg'}

def enabled(db=None,connection=None):
    if connection is not None:
        row=connection.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
    else:
        with db() as c:row=c.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
    return bool(row and json.loads(row['payload']).get('missing_nutrients_as_zero',False))

def ready(e):
    if e.get('status')=='processed':return True
    # Nutrient data may be absent even though identity and amount were resolved.
    q=e.get('quantity') or {}
    return e.get('status')=='needs_review' and q.get('unit')=='g' and q.get('value',0)>0 and bool(e.get('food')) and e.get('source',{}).get('provider') in ('BLS','Manual','Open Food Facts')

def assumable_qualifier(value):
    if value is None:return True
    if not isinstance(value,str):return False
    value=''.join(value.upper().split())
    if not value:return True
    token=r'(?:TR|TRACE|TRACES|SPUR|SPUREN|(?:<=|<|≤)?(?:LOD|LOQ))'
    return bool(re.fullmatch(token+r'(?:(?:OR|ODER|AND|UND|/|,|;)'+token+r')*',value))


def fill(values,water_unit='g'):
    result={k:dict(v) for k,v in values.items()}
    for key,unit in ZERO_UNITS.items():
        old=result.get(key)
        if old is None or old.get('value') is None and assumable_qualifier(old.get('qualifier')):
            result[key]={'value':0,'unit':water_unit if key=='dietaryWater' else unit,'assumed':True}
    return result

OFF_MAP = {'energy-kcal':('dietaryEnergyConsumed','kcal'), 'carbohydrates':('dietaryCarbohydrates','g'), 'fiber':('dietaryFiber','g'), 'sugars':('dietarySugar','g'), 'fat':('dietaryFatTotal','g'), 'saturated-fat':('dietaryFatSaturated','g'), 'proteins':('dietaryProtein','g'), 'sodium':('dietarySodium','g'), 'caffeine':('dietaryCaffeine','g')}
