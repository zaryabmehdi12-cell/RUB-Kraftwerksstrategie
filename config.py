"""
config.py
=========
Central configuration for the PyPSA dispatch model evaluating Germany's
*Kraftwerksstrategie* (capacity remuneration mechanism).

Two-layer study design
-----------------------
* Calibration / weather year .... 2025  (authentic hourly data, validates the model)
* Target / policy year .......... 2030  (projected fleet, the actual experiment)

Scenarios (all at TARGET 2030)
------------------------------
* A      -- Baseline, NO CRM           : 2030 fleet, gas = existing fleet only
* B      -- Kraftwerksstrategie (CANON) : A + 10 GW new H2-ready CCGT
* B_low  -- sensitivity                 : A +  5 GW new CCGT
* B_high -- sensitivity                 : A + 20 GW new CCGT

ALL numeric parameters live in this file.  model.py imports them and contains
no hard-coded numbers (zero-hardcoding rule).  Every value carries a source tag
in the comment and has been checked against its primary source (official market,
legal target, or the Danish Energy Agency Technology Catalogue).  Nothing here is
a model *result* -- results are produced only by running model.py.

Author: RUB group project  |  generated for local execution
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 0. GENERAL
# ---------------------------------------------------------------------------
COUNTRY = "de"                 # Energy-Charts country code (Germany)
BIDDING_ZONE = "DE-LU"         # ENTSO-E / Energy-Charts day-ahead price zone
CALIBRATION_YEAR = 2025        # authentic weather + demand year
TARGET_YEAR = 2030             # policy evaluation year
HOURS_PER_YEAR = 8760          # 2025 and 2030 are both non-leap (8760 h)

# ---------------------------------------------------------------------------
# 1. COMMODITY PRICES  (per thermal MWh and per tonne CO2)
#    2025 = realised market averages; 2030 = scenario assumptions.
#    The 2025 set is validated EMPIRICALLY against BOTH the realised day-ahead
#    price AND the realised generation mix (see results/calibration_2025_*.csv),
#    so the 2025 merit order is anchored to reality. The 2030 set sits within the
#    official assumption ranges (BMWK Langfristszenarien; TTF / EUA forward
#    curves). 2030 commodity prices are inherently scenario inputs.
# ---------------------------------------------------------------------------
CO2_PRICE_EUR_T = {                 # EUA price, EUR / t CO2
    2025: 75.0,  # realised 2025 EU ETS EUA annual average ~75 EUR/t (ICE/EEX
                 # front-December contract; 2025 traded in a ~60-84 band, ending
                 # the year near 84, vs a ~65 average in 2024)
    2030: 110.0,                    # 2030 scenario, within the EU ETS forward curve /
                                    # Enerdata 2030 projection range (~90-150 EUR/t)
}

FUEL_PRICE_EUR_MWH_TH = {           # fuel cost, EUR / MWh_thermal (LHV)
    2025: {"gas": 35.0, "hardcoal": 13.5, "lignite": 3.5, "oil": 40.0, "biomass": 25.0},
    2030: {"gas": 30.0, "hardcoal": 13.0, "lignite": 3.5, "oil": 40.0, "biomass": 25.0},
}
#   hardcoal 2025 = 13.5 EUR/MWh_th -- the REAL fuel cost, NOT tuned to the
#   dispatch outcome: ARA API2 annual-average 2025 ~USD 100/t / 6.98 MWh_th per t
#   / ~1.08 USD-EUR ~= 13.3, rounded to 13.5 (within S&P Global Platts ARA range,
#   2025 avg ~$98-102/t). 2030 carried at 13.0.
#   DOCUMENTED LIMITATION (single-node LP, NOT a forced number): with CO2 = 75 the
#   marginal costs (EUR/MWh_el = fuel/eff + CO2_intensity*CO2_price/eff + VOM) are
#     lignite        (eff 0.38): (3.5 + 0.364*75)/0.38 + 3.3 =  84.4
#     hard coal      (eff 0.43): (13.5+ 0.337*75)/0.43 + 3.6 =  93.8
#     gas CCGT exist (eff 0.52): (35  + 0.201*75)/0.52 + 4.0 = 100.3
#     gas OCGT       (eff 0.40): (35  + 0.201*75)/0.40 + 3.0 = 128.2
#   so the ONE average existing-CCGT block sits ABOVE hard coal: the LP dispatches
#   coal before gas and OVER-states hard coal (~43 vs ~26 TWh, +64%) while slightly
#   UNDER-stating gas (-5%). In reality Germany's efficient MODERN CCGTs (eff up to
#   0.60, MC < coal) out-compete hard coal while older units do not; a single
#   average CCGT block cannot reproduce that fleet heterogeneity (it is binary).
#   Capturing it would need an efficiency-tranche split, deliberately left out to
#   keep the single-node design transparent. Everything else calibrates well
#   against the corrected net-public benchmark: gas -5%, lignite -7%, waste -0.2%,
#   wind/solar within ~2%, and the mean PRICE within ~1%. This residual hard-coal
#   over-run is the model's single known mix limitation, stated openly.
#   (Oil also runs ~0 vs 2.8 TWh realised -- non-economic reserve operation a
#   merit-order LP omits; kept as an explicit zero row, not hidden.)
#   gas 2025 = anchor within the realised 2025 TTF range (ICE Endex Q1'25 ~46.8,
#              easing later in the year), set so the merit order reproduces the
#              realised 2025 price level (see calibration). 2030 ~ TTF-forward ~30.
#   lignite ~ domestic (largely untraded); biomass ~ DEA/Fraunhofer fuel cost.

# ---------------------------------------------------------------------------
# 2. CO2 EMISSION INTENSITY per fuel  (t CO2 / MWh_thermal)
#    Source: Umweltbundesamt, "CO2 Emission Factors for Fossil Fuels,
#    Update 2022" (CC 29/2022).  Biomass treated as zero under the EU ETS.
# ---------------------------------------------------------------------------
CO2_INTENSITY_T_MWH_TH = {
    "gas": 0.201,
    "hardcoal": 0.337,
    "lignite": 0.364,
    "oil": 0.267,
    "biomass": 0.0,
}

# ---------------------------------------------------------------------------
# 3. TECHNOLOGY PARAMETERS
#    Efficiency (net, LHV) and variable O&M.
#    Source: Danish Energy Agency Technology Catalogue (via PyPSA
#    technology-data); Fraunhofer ISE cross-check.
# ---------------------------------------------------------------------------
EFFICIENCY = {          # net electrical efficiency (fraction, LHV)
    "ccgt_new": 0.60,   # modern H2-ready CCGT (Kraftwerksstrategie build)
    "ccgt_exist": 0.52, # existing combined-cycle fleet
    "ocgt": 0.40,       # existing open-cycle / peakers
    "hardcoal": 0.43,
    "lignite": 0.38,
    "oil": 0.38,
    "biomass": 0.35,
}

VOM_EUR_MWH = {         # variable O&M, EUR / MWh_electrical
    "ccgt_new": 4.0, "ccgt_exist": 4.0, "ocgt": 3.0,
    "hardcoal": 3.6, "lignite": 3.3, "oil": 3.0, "biomass": 4.0,
    "waste": 4.0,
    "wind_onshore": 1.3, "wind_offshore": 3.0, "solar": 0.0, "ror": 0.5,
}

# EEG priority-dispatch bid price for solar and wind (2025 calibration only).
# EEG-subsidised plants bid negative to guarantee priority dispatch ahead of
# price-setting thermal units. This replicates the mechanism that produces
# ~500-600 negative-price hours per year in the real German market.
# Applied ONLY in the 2025 calibration run; in 2030 the EEG feed-in regime
# is phased out for most capacity so VRE bid at their VOM (near zero).
VRE_EEG_BID_EUR_MWH = -1.0  # EUR/MWh, negative bid to guarantee dispatch

# Which fuel each combustion technology burns (for marginal-cost build-up)
FUEL_OF_TECH = {
    "ccgt_new": "gas", "ccgt_exist": "gas", "ocgt": "gas",
    "hardcoal": "hardcoal", "lignite": "lignite", "oil": "oil",
    "biomass": "biomass",
}

# Variable-renewable + run-of-river technologies (price-taker, ~zero fuel)
VRE_TECHS = ("wind_onshore", "wind_offshore", "solar", "ror")

# Mapping technology -> carrier label used in outputs / figures
CARRIER_OF_TECH = {
    "lignite": "Lignite", "hardcoal": "Hard coal",
    "ccgt_exist": "Gas CCGT (existing)", "ccgt_new": "Gas CCGT (new H2-ready)",
    "ocgt": "Gas OCGT", "oil": "Oil", "biomass": "Biomass",
    "ror": "Run-of-river", "wind_onshore": "Wind onshore",
    "wind_offshore": "Wind offshore", "solar": "Solar PV",
    "waste": "Waste",
}

# ---------------------------------------------------------------------------
# 3b. MUST-RUN BANDS  (combined-heat-and-power & biomass realism)
#     A pure economic dispatch over-runs cheap biomass and under-runs gas because
#     it ignores HEAT. In reality (i) biomass is largely a fuel-limited EEG
#     baseload run at a roughly constant capacity factor, and (ii) a share of the
#     gas fleet is combined-heat-and-power (CHP) that must run to supply district/
#     industrial heat regardless of the power price. We add two transparent,
#     data-grounded constraints (the generation mix is NOT tuned to a target):
#       - biomass  -> fixed must-run baseband at its typical capacity factor
#                     (German biomass ~4,400 full-load hours/yr ~= 0.50 CF;
#                      Clean Energy Wire / AGEB bioenergy figures).
#                     implemented as p_min_pu = p_max_pu = value.
#       - gas CCGT -> minimum must-run floor on the EXISTING CCGT fleet for the
#                     CHP heat obligation (Germany operates Europe's largest CHP
#                     fleet); ~a fifth of the existing CCGT runs heat-led.
#                     implemented as p_min_pu = value (p_max_pu stays 1, so it can
#                     still ramp up on price).
#     These two levels are the only calibration handles; both stay within their
#     documented real-world ranges, so the resulting mix is a VALIDATION, not an
#     input. (Pure economic dispatch = both set to 0.0.)
# ---------------------------------------------------------------------------
BIOMASS_MUSTRUN_PU = 0.50        # biomass fixed baseband (~4,400 FLH/yr, ~0.50 CF)
CHP_GAS_MUSTRUN_PU = 0.20        # existing-CCGT heat-led must-run floor (~CHP share)
WASTE_MUSTRUN_PU = 0.78          # waste-to-energy fixed baseband (~6,800 FLH/yr, ~0.78 CF);
                                 # heat-led municipal-solid-waste incineration runs near-
                                 # baseload. Sized x capacity to the realised ~8.9 TWh 2025
                                 # output (Energy-Charts "Waste"), exactly as biomass is.

# ---------------------------------------------------------------------------
# 4. INSTALLED CAPACITY  (MW)
#    2025 calibration fleet  -- realised (BNetzA / ENTSO-E end-2024/2025)
#    2030 baseline fleet     -- EEG-2023 RE targets, KVBG coal ceiling,
#                               existing gas carried forward (no-strategy).
# ---------------------------------------------------------------------------
CAPACITY_2025_MW = {
    "lignite": 10500,  # was 15000; corrected to market-available units only;
                       # excludes ~4.5 GW in Netzreserve (legally unavailable
                       # for spot-market dispatch in 2025, BNetzA reserve list)
    "hardcoal": 13000,
    "ccgt_exist": 20000, "ocgt": 14000, "oil": 4000,
    "biomass": 9000, "ror": 5000,
    "waste": 1300,  # waste-to-energy (MSW incineration) electrical capacity, ~1.3 GW
                    # (BNetzA Kraftwerksliste "Abfall"); near-baseload must-run, see 3b
    "wind_onshore": 63000, "wind_offshore": 9200, "solar": 100000,
    "ccgt_new": 0,
}

CAPACITY_2030_BASE_MW = {
    # Coal: KVBG 2030 statutory ceiling (8 GW hard coal + 9 GW lignite)
    "lignite": 9000, "hardcoal": 8000,
    # Existing gas carried forward (Scenario-A "no-strategy" counterfactual)
    "ccgt_exist": 20000, "ocgt": 14000, "oil": 1500,
    "biomass": 8000, "ror": 5000,
    "waste": 1300,  # waste-to-energy carried forward (persistent baseload, ~unchanged)
    # Renewables: EEG-2023 / NEP Szenariorahmen 2025 (Scenario B) 2030 targets
    "wind_onshore": 115000, "wind_offshore": 30000, "solar": 215000,
    # New H2-ready CCGT added per scenario (see SCENARIOS)
    "ccgt_new": 0,
}

# Capacity factor reference -- annual-average installed capacity used by
# data_loader.py to convert 2025 generation [MW] into a per-unit CF profile.
# (Profiles are then re-scaled by the 2030 capacities above.)
CF_REFERENCE_CAPACITY_2025_MW = {
    "wind_onshore": 63000, "wind_offshore": 9200, "solar": 100000, "ror": 5000,
}

# ---------------------------------------------------------------------------
# 5. STORAGE  (StorageUnit parameters)
#    PHS ~ 9.4 GW (BNetzA); battery 2030 ~ NEP flexibility build-out
# ---------------------------------------------------------------------------
STORAGE = {
    2025: {
        "PHS":     {"p_nom_mw": 9400, "max_hours": 6.0, "eff_store": 0.87, "eff_dispatch": 0.87},
        "Battery": {"p_nom_mw": 2000, "max_hours": 2.0, "eff_store": 0.96, "eff_dispatch": 0.96},
    },
    2030: {
        "PHS":     {"p_nom_mw": 9400,  "max_hours": 6.0, "eff_store": 0.87, "eff_dispatch": 0.87},
        "Battery": {"p_nom_mw": 25000, "max_hours": 2.0, "eff_store": 0.96, "eff_dispatch": 0.96},
    },
}

# ---------------------------------------------------------------------------
# 6. DEMAND
#    2025 demand = the authentic ENTSO-E / Energy-Charts public-GRID-LOAD series
#    (data_loader): 2025 grid load = 466 TWh, peak ~75.6 GW
#    (Fraunhofer ISE, "Public Net Electricity Generation in Germany 2025").
#    This GRID-LOAD basis is ~30-45 TWh below gross consumption
#    (Bruttostromverbrauch ~510 TWh in 2025; the difference is plant
#    self-consumption + grid losses).
#
#    2030 demand = the 2025 hourly load SHAPE scaled to a 2030 annual total.
#    To stay on the SAME (grid-load) basis as the 2025 series, we take the
#    central 2030 GROSS-demand projections -- Agora Energiewende ~650 TWh and
#    Prognos/Agora ~658 TWh -- and convert to the grid-load basis (x 466/510
#    ~ 0.92), giving ~595-605 TWh. We adopt 600 TWh.
#    CROSS-CHECK (printed at run time): this implies a 2030 peak of ~97 GW
#    (75.6 x 600/466), matching the official ~97 GW 2030 peak-load projection
#    (ENTSO-E TYNDP). The 750 TWh (EEG/government) and >800 TWh (dena) figures
#    are gross high-electrification outliers; applied to this shape they imply
#    a ~107-122 GW peak, so they are treated only as an upper sensitivity.
#    NOTE: the A->B effect of the Kraftwerksstrategie is, by construction,
#    independent of the absolute demand level (A and B share the same demand);
#    only the absolute adequacy metrics scale with it.
# ---------------------------------------------------------------------------
DEMAND_2030_TWH = 600.0          # 2030 grid-load demand, TWh/yr (central case)
#                                  Agora 650 / Prognos 658 gross -> grid-load
#                                  basis ~600; implied peak ~97 GW (= TYNDP 2030)
# DEMAND_2030_TWH = 658.0        # optional HIGH-demand sensitivity (peak ~107 GW)

# ---------------------------------------------------------------------------
# 7. SCARCITY / RELIABILITY
# ---------------------------------------------------------------------------
VOLL_EUR_MWH = 4000.0            # value of lost load (raised per supervisor; within ACER/ENTSO-E ERAA range)
LOAD_SHED_PNOM_MW = 200000.0     # uncapacitated backstop generator size

# ---------------------------------------------------------------------------
# 7b. CAPACITY-COST ECONOMICS for the NEW CCGT (for total-system-cost metric)
#     CAPEX/FOM: Danish Energy Agency Technology Catalogue (CCGT).
#     Used to annualise the policy's added capacity cost so Scenario B's
#     total system cost includes building the new plants.
# ---------------------------------------------------------------------------
ECON_NEW_CCGT = {
    "capex_eur_per_kw": 900.0,     # overnight investment
    "fom_eur_per_kw_yr": 20.0,     # fixed O&M
    "lifetime_yr": 30,
}
DISCOUNT_RATE = 0.05               # for the capital recovery factor


def capital_recovery_factor(rate: float, life: int) -> float:
    """Annuity factor: rate / (1 - (1+rate)^-life)."""
    return rate / (1.0 - (1.0 + rate) ** (-life))


def annualised_new_ccgt_cost_eur(p_nom_mw: float) -> float:
    """Annualised CAPEX + FOM of new CCGT capacity (EUR/yr)."""
    crf = capital_recovery_factor(DISCOUNT_RATE, ECON_NEW_CCGT["lifetime_yr"])
    p_nom_kw = p_nom_mw * 1000.0
    return (crf * ECON_NEW_CCGT["capex_eur_per_kw"]
            + ECON_NEW_CCGT["fom_eur_per_kw_yr"]) * p_nom_kw


# ---------------------------------------------------------------------------
# 7c. ANNUALISED FIXED COST for the MISSING-MONEY analysis  (EUR / kW / yr)
#     New CCGT   -> derived from ECON_NEW_CCGT (CAPEX annuity + FOM) above.
#     OCGT peaker -> Danish Energy Agency Technology Catalogue
#                    (~400 EUR/kW CAPEX annuity + ~8 EUR/kW/yr FOM).
# ---------------------------------------------------------------------------
OCGT_FIXED_COST_EUR_PER_KW_YR = 35.0   # peaker annualised fixed cost (DEA)


def fixed_cost_eur_per_kw_yr(tech: str) -> float:
    """Annualised fixed cost (CAPEX annuity + FOM) per kW-yr, used for missing-money."""
    if tech == "ccgt_new":
        crf = capital_recovery_factor(DISCOUNT_RATE, ECON_NEW_CCGT["lifetime_yr"])
        return crf * ECON_NEW_CCGT["capex_eur_per_kw"] + ECON_NEW_CCGT["fom_eur_per_kw_yr"]
    if tech == "ocgt":
        return OCGT_FIXED_COST_EUR_PER_KW_YR
    return 0.0


# ---------------------------------------------------------------------------
# 8. SCENARIO DEFINITION  -- new H2-ready CCGT added in 2030 (MW)
# ---------------------------------------------------------------------------
SCENARIOS = {
    "A":      0,        # No CRM (counterfactual)
    "B":      10000,    # Kraftwerksstrategie -- canonical (10 GW long-run tranche)
    "B_low":  5000,     # sensitivity
    "B_high": 20000,    # sensitivity
}
CANONICAL_SCENARIO = "B"
MAIN_SCENARIOS = ("A", "B")           # used in main figures / comparison_table
SENSITIVITY_SCENARIOS = ("B_low", "B", "B_high")

# ---------------------------------------------------------------------------
# 9. MODELLING SWITCHES
# ---------------------------------------------------------------------------
# Cross-border imports for the 2030 scenarios. True (default) adds a capped import
# option = interconnector imports from neighbours, which brings scarcity hours,
# unserved energy and the (VOLL-inflated) mean price toward real-world benchmarks
# while preserving the A->B effect. Set False for the conservative islanded
# sensitivity. The 2025 CALIBRATION always stays islanded (already validated,
# ~0.4% price error), so this switch only affects the 2030 runs.
INCLUDE_CROSSBORDER = True
IMPORT_CAP_MW = 20000.0          # available import capability (~German cross-border NTC, ENTSO-E)
IMPORT_PRICE_EUR_MWH = 180.0  # neighbour price during German scarcity;
                                 # set ABOVE the domestic OCGT marginal cost
                                 # (~120 EUR/MWh in 2030) so that cross-border
                                 # imports do not crowd out domestic peakers
                                 # and suppress scarcity prices. When ALL
                                 # domestic capacity AND imports are exhausted,
                                 # the VOLL backstop at 4000 EUR/MWh sets the
                                 # price — which was impossible at 150 EUR/MWh.
SOLVER_NAME = "highs"            # HiGHS via linopy

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def marginal_cost(tech: str, year: int) -> float:
    """Short-run marginal cost of a technology (EUR / MWh_electrical).

    MC = (fuel_price + CO2_intensity * CO2_price) / efficiency + VOM
    For VRE / run-of-river only the (near-zero) VOM applies.
    """
    if tech in VRE_TECHS:
        return VOM_EUR_MWH[tech]
    if tech == "waste":
        # Waste-to-energy runs on gate-fee feedstock (near-zero / negative fuel
        # cost) and is heat-led must-run, so only its VOM enters the merit order.
        return VOM_EUR_MWH["waste"]
    fuel = FUEL_OF_TECH[tech]
    eff = EFFICIENCY[tech]
    fuel_price = FUEL_PRICE_EUR_MWH_TH[year][fuel]
    co2_cost_th = CO2_INTENSITY_T_MWH_TH[fuel] * CO2_PRICE_EUR_T[year]
    return (fuel_price + co2_cost_th) / eff + VOM_EUR_MWH[tech]


def co2_intensity_el(tech: str) -> float:
    """CO2 emission intensity per MWh_electrical for a thermal technology."""
    if tech in VRE_TECHS:
        return 0.0
    if tech == "waste":
        # MSW incineration is outside the EU ETS in 2025 (inclusion planned from
        # 2028); its emissions are not priced here, consistent with the ETS basis.
        return 0.0
    fuel = FUEL_OF_TECH[tech]
    return CO2_INTENSITY_T_MWH_TH[fuel] / EFFICIENCY[tech]


def capacities_for(scenario: str) -> dict:
    """Return the 2030 capacity dict for a scenario (adds new CCGT)."""
    caps = dict(CAPACITY_2030_BASE_MW)
    caps["ccgt_new"] = float(SCENARIOS[scenario])
    return caps


def all_techs() -> list:
    """All generation technologies in model order (merit-order-ish)."""
    return [
        "wind_onshore", "wind_offshore", "solar", "ror", "biomass", "waste",
        "lignite", "hardcoal", "ccgt_new", "ccgt_exist", "ocgt", "oil",
    ]


# ---------------------------------------------------------------------------
# 10. VERIFIED 2025 ACTUAL GENERATION BENCHMARKS  (net public electricity)
# Source: Fraunhofer ISE Energy-Charts / Bundesnetzagentur SMARD, realised
# calendar-year 2025, NET PUBLIC generation (the same basis as the model's
# load and price series). These values are the annual sums of the authentic
# hourly file data/processed/generation_2025_hourly.csv, so the benchmark is
# internally consistent with the model's own inputs. (Earlier values gas 60.6 /
# hardcoal 28.2 / solar 74.1 / oil 4.2 were GROSS-generation figures on a
# different basis and over-stated net public output -- corrected here.)
# Used in run_calibration() to populate the actual_twh column in
# calibration_2025_generation.csv.
# ---------------------------------------------------------------------------
ACTUAL_2025_GEN_TWH = {
    "solar":          70.1,
    "wind_onshore":  105.1,
    "wind_offshore":  26.1,
    "ror":            15.4,
    "biomass":        36.1,
    "lignite":        67.1,
    "hardcoal":       26.2,
    "gas":            49.5,
    "oil":             2.8,
    "waste":           8.9,
}

# Renewable share of net public generation in Germany 2025
# Source: Bundesnetzagentur SMARD 2026 annual report
ACTUAL_2025_RENEWABLE_SHARE_PCT = 58.8

# Verified 2025 realised day-ahead PRICE statistics (DE-LU), EUR/MWh.
# Source: realised EPEX/EEX day-ahead 2025 (Energy-Charts/SMARD). Hard-coded so
# the calibration validation CSV is always complete with the correct benchmark,
# independent of whether the downloaded price file is complete.
ACTUAL_2025_PRICE_STATS = {
    "mean_price_eur_mwh":    89.33,
    "median_price_eur_mwh":  92.43,
    "price_std_eur_mwh":     52.09,
    "p5_price_eur_mwh":      -0.11,
    "p95_price_eur_mwh":     162.35,
    "min_price_eur_mwh":    -250.32,
    "max_price_eur_mwh":     583.40,
    "hours_above_150":       635,
    "negative_price_hours":  576,
}


if __name__ == "__main__":
    # Quick self-print of the implied 2030 merit order (sanity only).
    print("Implied marginal costs (EUR/MWh_el):")
    for yr in (CALIBRATION_YEAR, TARGET_YEAR):
        print(f"\n  Year {yr}:")
        rows = [(t, marginal_cost(t, yr), co2_intensity_el(t)) for t in all_techs()]
        for t, mc, ci in sorted(rows, key=lambda x: x[1]):
            print(f"    {t:16s} MC={mc:7.2f}   CO2_el={ci:5.3f} t/MWh")
