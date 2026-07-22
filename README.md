# CentraXX Organisation Unit Import (YAML -> XML)

This project generates CentraXX import XML files from a YAML file.

Current support:

- Master data XML (`CatalogueData` with `OrganisationUnitCatalogueItem`) generates XML for orga units
- Users XML (`CatalogueData` with `Participant` and OU role assignments) generates XML organisation units role assignment to users
- Studies XML (`EffectData` with `FlexiStudy` basic fields) generates XML studie release to orgnisation units
- Storage location XML (`SampleLocationInstanceCatalogueItem`) generates XML to assign storage location to study's organisation units
- Workflow release is intentionally not part of this script and should be done manually in CentraXX.

## Install

```bash
/home/aminn/org_unit_imp/.venv/bin/pip install -r requirements.txt
```

## Run

```bash
/home/aminn/org_unit_imp/.venv/bin/python main.py \
	num_test \
	--input templates/org_unit_import.yaml \
	--output-dir output \
	--prefix rapid_elapse_test
```

This creates:

- `output/rapid_elapse_test_masterdata.xml`
- `output/rapid_elapse_test_users.xml`
- `output/rapid_elapse_test_studies.xml`
- `output/rapid_elapse_test_storage_locations.xml`
