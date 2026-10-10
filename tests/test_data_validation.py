from scripts.validate_data import validate
def test_dataset():
 errors,counts=validate('data/csv');assert not errors,errors;assert counts['customers']>=30 and counts['products']>=20 and counts['orders']>=60
