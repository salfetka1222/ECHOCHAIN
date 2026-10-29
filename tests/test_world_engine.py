import unittest

from engine.world_engine import Genome, evolve


class WorldEngineTests(unittest.TestCase):
    def test_default_genome_is_valid(self):
        genome = Genome()
        self.assertEqual(set(genome.to_dict()), {
            "stability", "energy", "resonance", "adaptation", "complexity"
        })
        self.assertTrue(all(0 <= value <= 100 for value in genome.to_dict().values()))

    def test_evolution_is_deterministic(self):
        parent = Genome()
        self.assertEqual(evolve(parent, "EC-ABC123", 1), evolve(parent, "EC-ABC123", 1))

    def test_evolution_changes_only_valid_values(self):
        result = evolve(Genome(), "EC-ABC123", 1)
        self.assertTrue(all(0 <= value <= 100 for value in result.to_dict().values()))

    def test_generation_must_be_positive(self):
        with self.assertRaises(ValueError):
            evolve(Genome(), "EC-ABC123", 0)

    def test_genome_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            Genome(energy=101).to_dict()


if __name__ == "__main__":
    unittest.main()
