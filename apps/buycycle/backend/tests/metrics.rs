use buycycle_backend::{contracts::Kind, metrics};
use chrono::{DateTime, Utc};
use serde_json::{Value, json};
fn now() -> DateTime<Utc> {
    "2026-10-17T12:00:00Z".parse().unwrap()
}
fn row(id: &str, kind: &str, name: &str, brand: &str, price: i64) -> Value {
    json!({"id":id,"kind":kind,"slug":id,"name":name,"brand":brand,"price":price,"first_seen":"2026-10-01","gone_at":null,"n_media":4,"desc_len":100})
}
fn disc(mut v: Value) -> Value {
    v["spec"]=json!(json!({"spec":{"wheel-type":"1372","complete-wheels-brakes-type":"1430","rim-material":"1433","wheel-system":"1435"}}).to_string());
    v
}
#[test]
fn wheel_comparables_exclude_self_gone_other_brake_and_material() {
    let mut rows = vec![
        disc(row("a", "wheels", "DT Swiss ERC 1400", "DT Swiss", 1000)),
        disc(row("b", "wheels", "DT Swiss ERC 1400", "DT Swiss", 2000)),
        disc(row("c", "wheels", "DT Swiss ERC 1400", "DT Swiss", 3000)),
        disc(row("d", "wheels", "DT Swiss ERC 1400", "DT Swiss", 9000)),
    ];
    let mut gone = disc(row("gone", "wheels", "DT Swiss ERC 1400", "DT Swiss", 50));
    gone["gone_at"] = json!("2026-10-10");
    rows.push(gone);
    let mut rim = disc(row("rim", "wheels", "DT Swiss ERC 1400", "DT Swiss", 50));
    rim["spec"] = json!(
        json!({"spec":{"complete-wheels-brakes-type":"1431","rim-material":"1433"}}).to_string()
    );
    rows.push(rim);
    let got = metrics::build(Kind::Wheels, rows, vec![], vec![], vec![], now());
    let a = got.iter().find(|r| r.id == "a").unwrap();
    assert_eq!(a.comparables, 3);
    assert_eq!(a.reference_price, Some(3000.));
    assert_eq!(a.average_ask, Some(4666.67));
    assert_eq!(a.wheel_system, "tubeless");
    assert_eq!(got.iter().find(|r| r.id == "rim").unwrap().comparables, 0);
    assert_eq!(a.next_up.as_ref().unwrap().price, 2000.);
}
#[test]
fn bike_year_window_is_one_year_and_unknown_matches_known() {
    let mut rows = Vec::new();
    for (id, year, price) in [
        ("a", Some(2024), 2000),
        ("b", Some(2023), 1000),
        ("c", Some(2025), 9000),
        ("d", Some(2022), 100),
        ("unknown", None, 3000),
    ] {
        let mut r = row(id, "bikes", "Specialized Tarmac SL7", "Specialized", price);
        r["year"] = json!(year);
        rows.push(r)
    }
    let got = metrics::build(Kind::Bikes, rows, vec![], vec![], vec![], now());
    let a = got.iter().find(|r| r.id == "a").unwrap();
    assert_eq!(a.comparables, 3);
    assert_eq!(a.reference_price, Some(3000.));
    assert_eq!(got.iter().find(|r| r.id == "d").unwrap().comparables, 2);
    assert_eq!(
        got.iter().find(|r| r.id == "unknown").unwrap().comparables,
        4
    );
}
#[test]
fn zscore_uses_population_stdev_with_low_sample_and_zero_spread_nulls() {
    let rows: Vec<_> = (1..=6)
        .map(|i| {
            disc(row(
                &format!("a{i}"),
                "wheels",
                "DT Swiss ARC 1100",
                "DT Swiss",
                i * 1000,
            ))
        })
        .collect();
    let got = metrics::build(Kind::Wheels, rows, vec![], vec![], vec![], now());
    let a = &got[0];
    assert_eq!(a.comparables, 5);
    assert_eq!(a.z_score, Some(-2.12));
    assert_eq!(a.dispersion, Some(75.));
    let rows = vec![
        disc(row("a", "wheels", "Enve SES", "Enve", 800)),
        disc(row("b", "wheels", "Enve SES", "Enve", 800)),
        disc(row("c", "wheels", "Enve SES", "Enve", 800)),
    ];
    assert!(
        metrics::build(Kind::Wheels, rows, vec![], vec![], vec![], now())
            .iter()
            .all(|r| r.z_score.is_none() && r.reference_price.is_none())
    );
}
#[test]
fn snapshot_drop_counts_when_original_price_hides_drop_and_no_history_stays_unknown() {
    let mut a = disc(row(
        "a",
        "wheels",
        "Syncros Capital SL 40 mm",
        "Syncros",
        2200,
    ));
    a["original_price"] = json!(2200);
    let h = vec![
        json!({"id":"a","day":"2026-08-01","price":3000}),
        json!({"id":"a","day":"2026-10-17","price":2200}),
    ];
    let got = metrics::build(Kind::Wheels, vec![a.clone()], vec![], h, vec![], now());
    let a = &got[0];
    assert_eq!(a.cut_per_day, Some(metrics::round(800. / a.days_listed, 2)));
    assert!(
        metrics::build(
            Kind::Wheels,
            vec![a_to_value()],
            vec![],
            vec![],
            vec![],
            now()
        )[0]
        .cut_per_day
        .is_none()
    );
    fn a_to_value() -> Value {
        disc(row("none", "wheels", "Zipp 404", "Zipp", 900))
    }
}
#[test]
fn mature_disappearance_share_and_relative_days_require_five_samples() {
    let mut rows = Vec::new();
    for i in 0..8 {
        let mut r = disc(row(
            &format!("m{i}"),
            "wheels",
            "Mavic Cosmic",
            "Mavic",
            1500,
        ));
        r["first_seen"] = json!("2026-08-01");
        if (1..=3).contains(&i) {
            r["gone_at"] = json!("2026-08-20")
        }
        if i >= 6 {
            r["gone_at"] = json!("2026-09-20")
        }
        rows.push(r)
    }
    let got = metrics::build(Kind::Wheels, rows, vec![], vec![], vec![], now());
    let a = &got[0];
    assert_eq!(a.sold_sample, Some(7));
    assert_eq!(a.sold_percent, Some(42.9));
    assert_eq!(
        a.versus_typical,
        Some(metrics::round(a.days_listed / 19., 2))
    );
}
#[test]
fn model_normalization_and_cost_defaults_match_legacy() {
    assert_eq!(
        metrics::model_key(
            &Kind::Wheels,
            "Syncros Capital SL 40 mm carbon disc 2024",
            "Syncros"
        ),
        "capital sl 40"
    );
    assert_eq!(
        metrics::model_key(
            &Kind::Bikes,
            "Specialized Tarmac SL7 Shimano Ultegra 2024",
            "Specialized"
        ),
        "tarmac sl7"
    );
    assert_eq!(metrics::default_costs(&Kind::Bikes)["sellfee"], 6.95);
    assert_eq!(metrics::default_costs(&Kind::Wheels)["pack"], 10.);
}
#[test]
fn rust_metrics_match_frozen_legacy_python_on_all_synthetic_characterization_rows() {
    let fixture: Value = serde_json::from_str(include_str!("metrics-golden.json")).unwrap();
    let tables = &fixture["tables"];
    let as_rows = |name: &str| tables[name].as_array().unwrap().clone();
    for (kind, name) in [(Kind::Bikes, "bikes"), (Kind::Wheels, "wheels")] {
        let actual = metrics::build(
            kind,
            as_rows("listing"),
            as_rows("detail"),
            as_rows("price_history"),
            as_rows("country_map"),
            now(),
        );
        let expected = fixture["expected"][name].as_object().unwrap();
        assert_eq!(actual.len(), expected.len());
        for row in actual {
            let value = serde_json::to_value(&row).unwrap();
            for (field, wanted) in expected[&row.id].as_object().unwrap() {
                let got = &value[field];
                if let (Some(g), Some(w)) = (got.as_f64(), wanted.as_f64()) {
                    assert!((g - w).abs() < 0.000001, "{} {field}: {g} != {w}", row.id);
                } else {
                    assert_eq!(got, wanted, "{} {field}", row.id);
                }
            }
        }
    }
}
#[test]
fn repeated_brand_boundaries_match_python_without_consuming_adjacent_occurrences() {
    assert_eq!(
        metrics::model_key(&Kind::Bikes, "Look Look 795 Blade RS", "Look"),
        "795 blade"
    );
    assert_eq!(
        metrics::model_key(&Kind::Bikes, "Look look-look 795 Blade", "Look"),
        "795 blade"
    );
}
#[test]
fn next_up_prefers_known_oldest_age_and_puts_unknown_age_last() {
    let subject = row("subject", "bikes", "Look 795 Blade", "Look", 1000);
    let mut unknown = row("unknown", "bikes", "Look 795 Blade", "Look", 2000);
    unknown["first_seen"] = Value::Null;
    let mut known = row("known", "bikes", "Look 795 Blade", "Look", 2000);
    known["first_seen"] = json!("2026-08-01");
    let got = metrics::build(
        Kind::Bikes,
        vec![subject, unknown, known],
        vec![],
        vec![],
        vec![],
        now(),
    );
    let next = got[0].next_up.as_ref().unwrap();
    assert!(next.url.ends_with("/known"));
    assert_eq!(next.ties, 1);
    assert_eq!(next.days_listed, Some(77));
}
#[test]
fn missing_or_invalid_asking_prices_are_retained_but_explicitly_quarantined() {
    let valid = row("valid", "bikes", "Look 795 Blade", "Look", 1000);
    let mut missing = valid.clone();
    missing["id"] = json!("missing");
    missing.as_object_mut().unwrap().remove("price");
    let mut null = valid.clone();
    null["id"] = json!("null");
    null["price"] = Value::Null;
    let mut zero = valid.clone();
    zero["id"] = json!("zero");
    zero["price"] = json!(0);
    let source = vec![valid, missing, null, zero];
    let before = source.clone();
    let report = metrics::report(metrics::CalculationInput {
        kind: Kind::Bikes,
        calculated_at: now(),
        rows: source.clone(),
        details: vec![],
        history: vec![],
        countries: vec![],
        runs: vec![],
    });
    assert_eq!(source, before);
    assert_eq!(report.items.len(), 1);
    assert_eq!(report.items[0].id, "valid");
    assert_eq!(report.items[0].comparables, 0);
    assert_eq!(report.quarantined.len(), 3);
    assert!(
        report
            .quarantined
            .iter()
            .all(|r| r.reason == "missing_or_invalid_price")
    );
    assert_eq!(report.alerts.len(), 0);
}
