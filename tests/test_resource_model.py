import json
import tempfile
import unittest
from pathlib import Path

from gantt_app.resource_model import (
    Resource, ResourceRepository, ResourceType, TeamPool,
)


class TestResourceModel(unittest.TestCase):
    def resource(self, resource_id="res_1", resource_type=ResourceType.NAMED,
                 **values):
        defaults = {
            "name": "John Doe",
            "role_type": "QA Manager",
            "weekly_capacity_hours": 40,
            "cost_per_hour": 75,
        }
        defaults.update(values)
        return Resource(id=resource_id, resource_type=resource_type, **defaults)

    def test_resource_round_trip_preserves_enum_and_mappings(self):
        resource = self.resource(
            team_memberships={"team_1": 0.6},
            assigned_project_ids=["Project A", "Project B"],
        )

        restored = Resource.from_dict(resource.to_dict())

        self.assertEqual(restored, resource)
        self.assertIs(restored.resource_type, ResourceType.NAMED)

    def test_resource_rejects_team_type_and_invalid_numbers(self):
        with self.assertRaises(ValueError):
            self.resource(resource_type=ResourceType.TEAM)
        with self.assertRaises(ValueError):
            self.resource(weekly_capacity_hours=-1)
        with self.assertRaises(ValueError):
            self.resource(team_memberships={"team_1": 1.01})

    def test_dynamic_team_capacity_uses_member_percentages(self):
        team = TeamPool(id="team_1", name="Core QA")
        full_time = self.resource(team_memberships={"team_1": 0.6})
        placeholder = self.resource(
            "res_2", ResourceType.GENERIC, name="QA Engineer #1",
            weekly_capacity_hours=30,
            team_memberships={"team_1": 0.5},
        )

        self.assertEqual(
            team.calculate_effective_capacity([full_time, placeholder]), 39)

    def test_fixed_team_capacity_overrides_members(self):
        team = TeamPool(id="team_1", name="Core QA",
                        is_fixed_capacity=True, fixed_hours=160)

        self.assertEqual(team.calculate_effective_capacity([self.resource()]), 160)

    def test_team_allocation_accepts_percentages_and_zero_detaches(self):
        repository = ResourceRepository()
        repository.add_resource(self.resource())
        repository.add_team(TeamPool(id="team_1", name="Core QA"))

        repository.set_team_allocation("res_1", "team_1", 60)
        self.assertEqual(repository.resources["res_1"].team_memberships,
                         {"team_1": 0.6})

        repository.set_team_allocation("res_1", "team_1", 0)
        self.assertEqual(repository.resources["res_1"].team_memberships, {})
        with self.assertRaises(ValueError):
            repository.set_team_allocation("res_1", "team_1", 101)

    def test_removing_team_cleans_every_resource_membership(self):
        repository = ResourceRepository()
        repository.add_team(TeamPool(id="team_1", name="Core QA"))
        repository.add_resource(self.resource(
            team_memberships={"team_1": 0.6}))

        repository.remove_team("team_1")

        self.assertNotIn("team_1", repository.teams)
        self.assertEqual(repository.resources["res_1"].team_memberships, {})

    def test_generic_swap_preserves_identity_and_allocations(self):
        repository = ResourceRepository()
        generic = self.resource(
            "placeholder", ResourceType.GENERIC,
            name="DevOps Engineer #1", role_type="DevOps",
            assigned_project_ids=["Project A"],
            team_memberships={"team_1": 0.4},
        )
        named = self.resource(
            "person", name="Jane Smith", role_type="Senior DevOps",
            weekly_capacity_hours=32, cost_per_hour=90,
            assigned_project_ids=["Project B"],
        )
        repository.add_resource(generic)
        repository.add_resource(named)

        replacement = repository.swap_generic("placeholder", "person")

        self.assertEqual(replacement.id, "placeholder")
        self.assertEqual(replacement.name, "Jane Smith")
        self.assertIs(replacement.resource_type, ResourceType.NAMED)
        self.assertEqual(replacement.team_memberships, {"team_1": 0.4})
        self.assertEqual(replacement.assigned_project_ids,
                         ["Project A", "Project B"])
        self.assertIn("person", repository.resources)

    def test_repository_persists_and_loads_resources_and_teams(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.json"
            repository = ResourceRepository(path)
            repository.add_resource(self.resource(
                assigned_project_ids=["Project A"]))
            repository.add_team(TeamPool(id="team_1", name="Core QA"))
            repository.set_team_allocation("res_1", "team_1", 25)

            repository.save_to_file()
            loaded = ResourceRepository(path)
            loaded.load_from_file()

            self.assertEqual(loaded.resources, repository.resources)
            self.assertEqual(loaded.teams, repository.teams)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[
                "resources"][0]["resource_type"], "named")

    def test_repository_rejects_non_object_or_malformed_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.json"
            repository = ResourceRepository(path)
            for contents in ("[]", '{"resources": {}}',
                             '{"resources": [{}]}'):
                path.write_text(contents, encoding="utf-8")
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    repository.load_from_file()

    def test_missing_repository_file_loads_an_empty_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ResourceRepository(Path(directory) / "missing.json")
            repository.add_resource(self.resource())

            repository.load_from_file()

            self.assertEqual(repository.resources, {})
            self.assertEqual(repository.teams, {})


if __name__ == "__main__":
    unittest.main()
