"""Seed data for the InfraPilot demo city.

Twelve interdependent assets, ~18 directed dependencies. Positions are fixed
(not computed) so the graph layout is byte-identical across reloads -- F1
requires deterministic layout for demo reliability.

Baseline `status` values encode pre-existing posture debt: the city does not
start perfect, which is both realistic and what makes the resilience score
start below 100 (see docs/SCORING.md).
"""

# --- Assets -----------------------------------------------------------------
# direction of dependencies: source SUPPLIES target.

ASSETS = [
    {
        "id": "power_station",
        "name": "Power Station",
        "type": "power",
        "criticality": 9,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 140.0,
        "position_y": 40.0,
        "software_inventory": {
            "os": "Windows Server 2019",
            "firmware": "GE Mark VIe 5.2",
            "packages": ["opcua-client@1.0.4", "modbus-tk@1.1.3", "numpy@1.26.0"],
        },
        "metadata": {"operator": "National Grid", "population_served": 850000},
    },
    {
        "id": "backup_generator",
        "name": "Backup Generator",
        "type": "power",
        "criticality": 3,
        "failure_threshold": 0.7,
        "status": "degraded",
        "position_x": 420.0,
        "position_y": 40.0,
        "software_inventory": {
            "os": "Embedded Linux 4.19",
            "firmware": "Cummins PowerCommand 3.8",
            "packages": ["canopen@2.0.0", "pyserial@3.5"],
        },
        "metadata": {"note": "Service overdue by 4 months", "population_served": 0},
    },
    {
        "id": "substation_a",
        "name": "Substation A",
        "type": "power",
        "criticality": 8,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 80.0,
        "position_y": 190.0,
        "software_inventory": {
            "os": "VxWorks 6.9",
            "firmware": "SEL-451 R320",
            "packages": ["iec61850-stack@2.3.1", "libssl@1.1.1w"],
        },
        "metadata": {"population_served": 240000},
    },
    {
        "id": "substation_b",
        "name": "Substation B",
        "type": "power",
        "criticality": 7,
        "failure_threshold": 0.7,
        "status": "degraded",
        "position_x": 380.0,
        "position_y": 190.0,
        "software_inventory": {
            "os": "VxWorks 6.9",
            "firmware": "SEL-451 R318",
            "packages": ["iec61850-stack@2.3.1", "libssl@1.1.1t"],
        },
        "metadata": {"note": "Running at reduced capacity", "population_served": 180000},
    },
    {
        "id": "vpn_gateway",
        "name": "VPN Gateway",
        "type": "network",
        "criticality": 4,
        "failure_threshold": 0.7,
        "status": "degraded",
        "position_x": 900.0,
        "position_y": 60.0,
        "software_inventory": {
            "os": "FortiOS 7.0.11",
            "firmware": "FortiGate 100F",
            "packages": ["openssl@3.0.8", "strongswan@5.9.5"],
        },
        "metadata": {"note": "Unpatched -- 2 advisories outstanding"},
    },
    {
        "id": "data_centre",
        "name": "Data Centre",
        "type": "digital",
        "criticality": 6,
        "failure_threshold": 0.7,
        "status": "degraded",
        "position_x": 1140.0,
        "position_y": 190.0,
        "software_inventory": {
            "os": "Ubuntu 22.04 LTS",
            "firmware": "Dell iDRAC 9 6.10",
            "packages": ["kubernetes@1.28.2", "postgres@15.4", "event-stream@3.3.6"],
        },
        "metadata": {"note": "Cooling redundancy fault on hall 2"},
    },
    {
        "id": "control_centre",
        "name": "Control Centre",
        "type": "control",
        "criticality": 9,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 620.0,
        "position_y": 330.0,
        "software_inventory": {
            "os": "Windows Server 2016",
            "firmware": "Siemens WinCC OA 3.18",
            "packages": ["scada-bridge@4.2.0", "node-ipc@10.1.1", "requests@2.31.0"],
        },
        "metadata": {"operator": "City Resilience Authority", "population_served": 850000},
    },
    {
        "id": "telecom_hub",
        "name": "Telecom Hub",
        "type": "comms",
        "criticality": 8,
        "failure_threshold": 0.7,
        "status": "degraded",
        "position_x": 960.0,
        "position_y": 330.0,
        "software_inventory": {
            "os": "Junos OS 21.4",
            "firmware": "MX960 21.4R3",
            "packages": ["netconf-client@2.1.0", "libssl@3.0.8"],
        },
        "metadata": {"note": "Partial fibre fault on ring 3", "population_served": 620000},
    },
    {
        "id": "traffic_mgmt",
        "name": "Traffic Management",
        "type": "transport",
        "criticality": 5,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 80.0,
        "position_y": 500.0,
        "software_inventory": {
            "os": "Debian 11",
            "firmware": "Siemens Sitraffic sX 3.4",
            "packages": ["utmc-adapter@1.4.2", "flask@2.3.3"],
        },
        "metadata": {"population_served": 400000},
    },
    {
        "id": "hospital",
        "name": "Hospital",
        "type": "health",
        "criticality": 10,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 340.0,
        "position_y": 500.0,
        "software_inventory": {
            "os": "Windows 10 IoT",
            "firmware": "Philips IntelliVue N.01.15",
            "packages": ["hl7-parser@2.2.0", "dicom-net@1.9.4", "openssl@3.0.8"],
        },
        "metadata": {"beds": 620, "population_served": 300000},
    },
    {
        "id": "water_treatment",
        "name": "Water Treatment Plant",
        "type": "water",
        "criticality": 8,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 620.0,
        "position_y": 500.0,
        "software_inventory": {
            "os": "Windows 7 Embedded",
            "firmware": "Allen-Bradley ControlLogix 32.011",
            "packages": ["ethernet-ip@1.2.0", "pycomm3@1.2.9"],
        },
        "metadata": {"population_served": 500000},
    },
    {
        "id": "emergency_services",
        "name": "Emergency Services",
        "type": "emergency",
        "criticality": 10,
        "failure_threshold": 0.7,
        "status": "healthy",
        "position_x": 920.0,
        "position_y": 500.0,
        "software_inventory": {
            "os": "RHEL 8.8",
            "firmware": "Motorola CommandCentral 7.2",
            "packages": ["cad-dispatch@5.1.0", "ua-parser-js@0.7.29"],
        },
        "metadata": {"population_served": 850000},
    },
]

# --- Dependencies -----------------------------------------------------------
# (source, target, dependency_type, weight)
# weight = probability/severity with which a failure of `source` propagates to `target`

DEPENDENCIES = [
    # Power distribution
    ("power_station", "substation_a", "power", 0.90),
    ("power_station", "substation_b", "power", 0.90),
    ("substation_a", "traffic_mgmt", "power", 0.85),
    ("substation_a", "hospital", "power", 0.50),
    ("substation_b", "water_treatment", "power", 0.75),
    ("substation_b", "telecom_hub", "power", 0.80),
    ("substation_b", "data_centre", "power", 0.80),
    ("backup_generator", "hospital", "power", 0.30),
    # Communications
    ("telecom_hub", "emergency_services", "comms", 0.85),
    ("telecom_hub", "control_centre", "comms", 0.60),
    ("data_centre", "control_centre", "comms", 0.50),
    ("vpn_gateway", "control_centre", "comms", 0.45),
    ("telecom_hub", "hospital", "comms", 0.40),
    # Operational / control
    ("control_centre", "substation_a", "operational", 0.75),
    ("control_centre", "substation_b", "operational", 0.35),
    ("control_centre", "traffic_mgmt", "operational", 0.80),
    ("control_centre", "water_treatment", "operational", 0.60),
    ("control_centre", "emergency_services", "operational", 0.50),
]

# --- Scenario presets (F2) --------------------------------------------------
# `tool_hint` documents which analyses a correct planner should choose; the SPOF
# preset is the F4 acceptance-criterion-2 proof (metrics only, no cascade).

SCENARIO_PRESETS = [
    {
        "id": "ransomware_control_centre",
        "label": "Ransomware on Control Centre",
        "query": "Simulate a ransomware attack on the Control Centre",
    },
    {
        "id": "transformer_substation_a",
        "label": "Transformer failure at Substation A",
        "query": "What happens if the transformer at Substation A fails?",
    },
    {
        "id": "fibre_cut_telecom",
        "label": "Fibre cut to Telecom Hub",
        "query": "Simulate a fibre cut taking out the Telecom Hub",
    },
    {
        "id": "vpn_compromise",
        "label": "VPN Gateway compromise",
        "query": "An attacker has compromised the VPN Gateway. What is the blast radius?",
    },
    {
        "id": "insider_water_plant",
        "label": "Insider attack on Water Plant",
        "query": "Simulate an insider attack on the Water Treatment Plant",
    },
    {
        "id": "plc_compromise",
        "label": "PLC compromise",
        "query": "Simulate a PLC compromise at the Water Treatment Plant",
    },
    {
        "id": "spof_analysis",
        "label": "Biggest single point of failure?",
        "query": "What is our biggest single point of failure?",
    },
]

# --- Mock OSSPrey findings (F6) ---------------------------------------------
# Same package on two assets, deliberately: the demo shows InfraPilot ranking
# them differently because the Control Centre cascade reaches the Hospital.

SUPPLY_CHAIN_FINDINGS = [
    {
        "id": "finding_node_ipc",
        "asset_id": "control_centre",
        "package": "node-ipc@10.1.1",
        "severity": "high",
        "behaviour": (
            "Package executes geolocation-conditional filesystem writes at install time. "
            "Behavioural signature matches known protestware payload, not a disclosed CVE."
        ),
    },
    {
        "id": "finding_event_stream",
        "asset_id": "data_centre",
        "package": "event-stream@3.3.6",
        "severity": "high",
        "behaviour": (
            "Transitive dependency introduced obfuscated payload targeting credential "
            "wallets. Maintainer handover pattern flagged as supply chain takeover."
        ),
    },
    {
        "id": "finding_ua_parser",
        "asset_id": "emergency_services",
        "package": "ua-parser-js@0.7.29",
        "severity": "medium",
        "behaviour": (
            "Compromised release published cryptominer and credential stealer via "
            "postinstall script. Version pinned below known-clean release."
        ),
    },
    {
        "id": "finding_libssl",
        "asset_id": "substation_b",
        "package": "libssl@1.1.1t",
        "severity": "low",
        "behaviour": (
            "Outdated TLS library on an end-of-life branch. No malicious behaviour "
            "observed; flagged for drift from approved baseline."
        ),
    },
]

SEVERITY_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}
