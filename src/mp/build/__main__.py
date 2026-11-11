"""`python -m mp.build`: race registry -> poll table -> pollster names and methods (in order)."""

from mp.build import polls, pollsters, races

print(races.build())
polls.main()
pollsters.main()
