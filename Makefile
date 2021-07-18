serve:
	source .env && run-alastor

update:
	pip install --upgrade --upgrade-strategy eager -e ".[dev]"

resetdb:
	dropdb alastor
	createdb -U alastor alastor

admin:
	psql -d alastor -c "update users set obj='{\"rank\": 3}'::json where email='admin@example.com'"
