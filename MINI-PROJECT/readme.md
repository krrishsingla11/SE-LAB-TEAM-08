# Online Marketplace for Handcrafted Goods (Team 08)

| Member | Roll No | Role |
|---|---|---|
| Krrish Singla | PES1UG24AM141 | Team Lead / Dev Lead |
| Kishan K Shenoy | PES1UG24AM138 | QA Lead |
| Kushal G | PES1UG24AM145 | Backend & DB |
| Namith Kumar C | PES1UG24AM171 | Frontend |

- Docs: SRS, SAD, STP in `templates/` and `diagrams/`
- Jira board: <paste your Jira link>
- Sprint 1: 27-31 Oct 2026 | Sprint 2: 2-7 Nov 2026
- Videos: `videos/`


## QA: how to run the tests

    py -m pip install -r requirements.txt
    py -m pytest tests -q -rxs
    py -m flake8 app tests --max-line-length 100

The 4 xfailed tests are features that are not built yet (order status, seller dashboard, sales reports).

Load test (needs the app running on port 5000, data from `py seed_demo.py`, JMeter 5.6):

    jmeter -n -t tests\performance\marketplace_load_test.jmx "-Jhost=127.0.0.1" -Jport=5000 -Jusers=100 -Jrampup=30 -Jduration=300 -l results_100.jtl -e -o report_100

Uptime check:

    py tests\performance\health_monitor.py --url http://127.0.0.1:5000/api/health --interval 2 --count 30

Results, deviations and open actions: `tests/DEVIATIONS.md`
