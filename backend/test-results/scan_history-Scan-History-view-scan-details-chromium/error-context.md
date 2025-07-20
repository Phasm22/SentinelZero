# Page snapshot

```yaml
- img "SentinelZero Logo"
- text: SentinelZero v1
- link "Back to Dashboard":
  - /url: /
- navigation:
  - link " Scan Types":
    - /url: /
  - link " Alert Settings":
    - /url: "#"
  - link " Scan History":
    - /url: /scan-history
  - link " Settings":
    - /url: /settings
- main:
  - link " Back to Dashboard":
    - /url: /
  - text:  Complete Scan History
  - table:
    - rowgroup:
      - row "Timestamp Type Hosts Vulns Actions":
        - cell "Timestamp"
        - cell "Type"
        - cell "Hosts"
        - cell "Vulns"
        - cell "Actions"
    - rowgroup:
      - row "Jul 18, 2025 19:55 IoT Scan 13 0  ":
        - cell "Jul 18, 2025 19:55"
        - cell "IoT Scan"
        - cell "13"
        - cell "0"
        - cell " ":
          - button ""
          - button ""
```