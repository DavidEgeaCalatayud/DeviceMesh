# ADR-0007: Windows agent in .NET

**Status:** Accepted

The Windows agent uses modern .NET and a Worker Service host. Platform collectors remain behind interfaces so host logic, protocol mapping and transport can be tested independently.
