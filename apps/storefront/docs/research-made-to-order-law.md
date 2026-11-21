# Made-to-order sales: returns, deposits and lead times under South African law

> This is research, not legal advice. Have a South African consumer-law attorney review it before DasKasas relies on it.

Researched 2026-11-21. Statute text comes from the Government Gazette copies on gov.za. Each section quoted here was checked against SAFLII's consolidated text. The only amendment SAFLII records to the CPA is National Credit Amendment Act 19 of 2014, which changed s71(1) only. ECTA Chapter VII is unchanged in SAFLII's consolidation. Regulation text is from GN R293 of 1 April 2011. Later amendments to those regulations were **not** checked.

## Summary

**The model under review:** the supplier makes a piece after the order, the customer picks fabric and colour, pays a deposit, gets a lead-time estimate, and pays the balance later.

- **There is no general "change of mind" return right in the CPA.** In store, a change-of-mind return is only ever retailer policy. CPA s20 lists four specific grounds, and none of them is "I don't like it". Online, ECTA s44 gives a 7-day cooling-off period from receipt of the goods. That period does not apply to goods "made to the consumer's specifications" or "clearly personalised" (ECTA s42(2)(f)).
- **"Custom" has two different legal tests.** They have different breadth:
  - **CPA "special-order goods"** (s1) are goods the supplier was required "to procure, create or alter specifically to satisfy the consumer's requirements". The test is broad. A piece DasKasas does not stock, made by the supplier only after the order and in the customer's chosen fabric, almost certainly qualifies. In *Adlam v Fabri* (High Court appeal, 2022) the court called the text "clear and unambiguous". In *NCC v Econocom* (National Consumer Tribunal, 2025) the tribunal treated a lounge suite ordered with a chosen size and fabric as special-order goods.
  - **ECTA "made to the consumer's specifications"** is narrower wording, and no South African decision on it was found. Choosing a fabric and colour from the supplier's standard range is arguable either way. It is more likely covered if the piece is not prefabricated and is made only on that choice. For comparison only, the EU text that uses the same phrase defines it as "non-prefabricated goods made on the basis of an individual choice of or decision by the consumer".
- **What "special-order" removes and what it keeps:**
  - It removes the CPA s17 right to cancel an advance order, and with it s17's "reasonable deposit / reasonable cancellation charge" regime. It also removes s47 (over-selling).
  - It does **not** remove the s55/s56 quality warranty, the s19 delivery rules, rejection on delivery for non-conformity (s19(5)(b) with s20(2)(b)), the s48 fairness control, or s65.
- **DasKasas can take a deposit and can keep part of it if the customer walks away.** For special-order goods the amount is set by the contract, not s17. The limits are:
  - CPA s48 and Regulation 44(3)(q) and (r): keeping a payment without a matching right for the customer is presumed unfair.
  - Conventional Penalties Act ss3–4: a court can cut a forfeiture that is "out of proportion to the prejudice".
  - Keeping the full deposit no matter when the customer cancels is the risky version. Forfeiture tied to real committed cost, in steps, is defensible.
- **Lay-by is the biggest structural risk.** If a deposit-then-balance sale counts as a lay-by under CPA s62:
  - The cancellation penalty is capped at **1%** (Regulation 34).
  - Failing to deliver can cost **double** the amount paid (s62(2)(b)(ii)).
  - Payments stay the consumer's property under s65.

  Structure the sale to stay outside the s62 elements, and get counsel to confirm.
- **An "estimate" is not an agreed date.** Online, ECTA s46 gives the customer the right to cancel on 7 days' notice if DasKasas misses the agreed period, or 30 days when nothing was agreed. In store, CPA s19(6) lets the customer cancel without penalty if delivery is tendered on a date other than the agreed one. State a latest delivery date.
- **The draft returns policy's "12 months for furniture under the CPA" is wrong as a statement of law.** The CPA return period for defective goods is **six months after delivery** (s56(2)). A 12-month guarantee is fine as DasKasas's own voluntary promise. Two parts of the draft conflict with s56(2):
  - It counts from the *date of purchase*. On a made-to-order lead time, that can leave the customer less than the six months after delivery that s56 gives.
  - It charges an upfront assessment fee. s56(2) says "without penalty and at the supplier's risk and expense".
- **VAT:** time of supply is the earlier of invoice or "any payment of consideration" (VAT Act s9(1)). A true security deposit is not payment until it is applied or forfeited. A deposit that is a part-payment of the price is safest treated as payment, so VAT is due when it is received. Confirm with the accountant.

---

## 1. Returns: CPA s16, s20 and the "custom" exclusion

**s20(2): the only statutory return grounds.** "the consumer may return goods to the supplier, and receive a full refund … if the supplier has delivered":

- (a) goods from direct marketing, rescinded in the s16 cooling-off period;
- (b) goods the consumer "did not have an opportunity to examine before delivery", rejected for the reasons in s19(5);
- (c) a mixture of goods, as in s19(8);
- (d) goods for a particular purpose communicated under s55(3), found unsuitable "within 10 business days after delivery".

s20(3) excludes goods that, after supply, "have been partially or entirely disassembled, physically altered, permanently installed …". Returns under s20 must be made "within 10 business days after delivery" (s20(4)). s20 is "in addition to" the s56 defect right (s20(1)).

**No change-of-mind ground.** No change-of-mind ground exists in the CPA for in-store purchases. The current 30-day change-of-mind return is DasKasas policy. A promise in the policy is binding as a contract term, so the "bespoke vs standard made-to-order" line in `web/src/lib/customer-policies.ts` matters.

**s16 (direct marketing cooling-off):** a customer may rescind "a transaction resulting from any direct marketing" within five business days. "Direct marketing" means to "approach a person, either in person or by mail or electronic communication" to promote goods (s1). An order the customer starts on the website is not direct marketing. DasKasas messaging a customer to offer a piece can be. s16 does not apply where ECTA s44 applies (s16(1)).

**s20 has no "custom" exclusion.** The "except custom items" rule people hear about comes from two other places:

- **CPA s17(1):** "This section does not apply … in respect of any special-order goods". This covers cancelling an *order*, not returning delivered goods.
- **ECTA s42(2)(f):** the cooling-off exclusion for online sales (§6).

**Definition (CPA s1):** "'special-order goods' means goods that a supplier expressly or implicitly was required or expected to procure, create or alter specifically to satisfy the consumer's requirements".

**Authority on what that covers:**

- ***Adlam v Fabri South Africa (Pty) Ltd*** [2022] ZAGPJHC 206 (full-bench appeal; reportable: no).
  - The consumer argued the goods "were ordered from a catalogue and the specifications of the standard goods were not altered" ([32]). She also argued for a purposive reading limiting the term to goods "of use only to that particular consumer" ([38]).
  - The court held that the text of s17, read with the definition, "is clear and unambiguous" ([42]). It found the goods were special-order "in that they are designed and created specifically to satisfy the appellant's requirements" ([43]). It also found they "were only of use to the appellant" ([52]).
  - The facts were stronger than DasKasas's: bespoke designs from floor plans, revised at the customer's request ([47]–[51]).
  - The supplier's argument also leaned on commentary (Naudé & Eiselen) saying goods a supplier must import because it "does not ordinarily stock" them are "procured" to satisfy the consumer ([39]). That is **secondary support only**. The court did not expressly adopt it.
- ***NCC v Econocom 357 (Pty) Ltd t/a Leather Gallery*** NCT/388029/2025/73(2)(b) (8 June 2025).
  - A furniture retailer took a 50% deposit on a "special order item, a lounge suite" ([34]). The customer then changed size and fabric ([36], [65]).
  - The tribunal applied the special-order definition without analysing it ([63]). The matter was unopposed.

**Assessment:**

- Under the CPA definition, a piece DasKasas does not stock, made by the supplier after the order in a customer-chosen fabric and colour, is very likely special-order goods. DasKasas "procure[s]" it and the supplier "create[s]" it "specifically to satisfy the consumer's requirements".
- The weakest case is a standard frame in a standard fabric that the supplier would make anyway. Even there, "procure … specifically" reads literally onto any non-stocked item.
- **Policy tension:** the storefront's own draft says a piece "made to a … fabric, or finish chosen for your order" cannot be returned for a change of mind. It also says a "standard made-to-order piece is a catalogue piece with a lead time". A fabric-and-colour pick falls in the first bucket under the draft's own words. Decide which bucket these pieces belong in.

## 2. Cancelling an order and keeping a deposit: CPA s17 and Regulation 5

**s17(2) and (3).** "a consumer has the right to cancel any advance booking, reservation or order for any goods". The supplier "may (a) require payment of a reasonable deposit in advance; and (b) impose a reasonable charge for cancellation".

**s17(4).** A charge is unreasonable "if it exceeds a fair amount in the circumstances, having regard to":

- (a) the nature of the goods;
- (b) the length of notice;
- (c) the potential "to find an alternative consumer";
- (d) "the general practice of the relevant industry".

**s17(5).** No fee where the consumer cannot honour the order "because of the death or hospitalisation" of the person it was made for.

**Regulation 5 is not the s17 regulation.** Reg 5 is headed "Maximum duration for fixed-term consumer agreements" and applies "for purposes of section 14(3)" to fixed-term agreements. Its factor list repeats s17(4)(a)–(d) as items (g)–(j). It is useful as an analogy for what is "reasonable", but it does not govern a once-off furniture sale. No regulation caps a s17 charge.

**Guidance on s17:**

- **NCC Explanatory Note 4 of 2023:**
  - "The supplier is entitled to charge a cancellation penalty where the decision by the consumer to cancel … rests solely on the consumer" (3.3).
  - The supplier may not charge one where cancellation follows the supplier tendering on different terms (3.4, s19(6)).
- **CGSO Advisory Note 12** [2021] ZACGSO 12 (ombud guidance, not binding law) recommends:
  - a deposit "proportionate to the loss that a supplier is likely to suffer";
  - "a stepped scale of forfeiture … in proportion to the length of notice given".

**Does s17 apply to special-order goods?** No. s17(1) excludes them, and *Adlam* [54] confirms it. Two consequences follow:

- The customer has **no statutory right to cancel**. Cancelling without contractual grounds is a repudiation, and DasKasas may hold the customer to the contract (*Adlam* [56], [63]–[65]).
- The deposit and forfeiture terms are governed by contract, then the CPA's general fairness rules (§9), then the Conventional Penalties Act.
  - In *Adlam* the court enforced "Refunds are only available in case of a breach of contract by FABRI" ([61]–[63]).
  - s48 and the Penalties Act were not decided on appeal.

**Practical shape:** take a deposit that covers what DasKasas actually commits to the maker, such as fabric cut and frame started. Then:

- before the maker starts, refund less a small actual admin cost;
- after that, forfeit only up to the deposit.

Disclose this before payment, and in the s49 conspicuous manner because it limits the customer's rights.

## 3. Holding the deposit: CPA s65

**s65(2):** "When a supplier has possession of any prepayment, deposit, membership fee, or other money, or any other property belonging to or ordinarily under the control of a consumer, the supplier":

- "(a) must not treat that property as being the property of the supplier";
- "(b) … must exercise the degree of care, diligence and skill that can reasonably be expected of a person responsible for managing any property belonging to another person"; and
- "(c) is liable to the owner … for any loss".

Banks are exempt (s65(1)). A liquidator must trace such money for the consumer (s65(3)).

**Reading it:**

- **Does it cover every deposit?** It is unclear whether "belonging to … a consumer" qualifies "deposit". If it does, s65 bites only on money that still belongs to the consumer, such as lay-by payments, which s62(1)(a) expressly makes the consumer's property "subject to section 65". If it does not, every deposit is covered.
- **Ombud and court in *Adlam*.** The CGSO relied on s65 and told the supplier it "may not treat the complainant's money as belonging to you" ([19]). The courts did not rule on s65.
- **No retailer rules.** No regulation or guidance was found on how a general retailer must hold deposits. The only s65 rule in the 2011 Regulations is reg 22, for auctioneers.
- **Use as working capital.** On the cautious reading, using deposits as general working capital is a breach of s65(2)(a). Paying the maker for *that customer's* piece is arguably a careful use for the consumer's benefit, but there is no authority on it.
- **Low-cost mitigation:** a separate deposits account, and paying the maker from it only for the matching order.

## 4. Lead times and late delivery: CPA s19 and ECTA s46

**Which rule applies.** CPA s19 "does not apply to … a transaction if the performance of that transaction is governed by section 46 of the [ECTA]" (s19(1)(b)). So s46 governs online orders and s19 governs showroom orders.

**ECTA s46 (online):**

- (1) "The supplier must execute the order within 30 days after the day on which the supplier received the order, unless the parties have agreed otherwise."
- (2) "Where a supplier has failed to execute the order within 30 days or within the agreed period, the consumer may cancel the agreement with seven days' written notice."
- (3) If the goods are unavailable, the supplier "must immediately notify the consumer … and refund any payments within 30 days".
- **Effect:** a lead time longer than 30 days must be *agreed*, so put it in the order. If DasKasas misses it, the customer can cancel. s46(2) does not spell out a refund. Restitution follows under the general law; this is an inference, so confirm it with counsel. A clause keeping the deposit in that case would conflict with Reg 44(3)(b) and (q).
- ECTA s43(1)(l) also requires the website to state "the time within which the goods will be dispatched or delivered".

**CPA s19 (showroom):**

- **Delivery date.** It is an implied condition that the supplier delivers "on the agreed date and at the agreed time, if any, or otherwise within a reasonable time" (s19(2)(a)(i)).
- **Wrong date.** If the supplier tenders delivery "on a date or at a time other than as agreed", the consumer may "cancel the agreement without penalty" (s19(6)(c)).
- **Refund with interest.** Payments for unsolicited goods are recoverable with interest under s21(9). The NCC reads s19(6)(c) with s21 so that the consumer gets "the full amount paid … and interest" (Explanatory Note 4/2023, 3.4).
- **Inspection on delivery.** On tender of delivery, the consumer may examine whether special-order goods "reasonably conform to the material specifications of the special order" (s19(5)(b)). Rejected goods are returnable for a full refund (s20(2)(b)), as *Econocom* [72] confirms.
- **Risk.** Goods stay at the supplier's risk until delivery is accepted (s19(2)(c)).

**Estimates.** An estimate is not an "agreed date". Without one, "reasonable time" applies, and a missed estimate gives no clean right to cancel. That uncertainty cuts both ways.

- Regulation 44(3)(p) presumes unfair a term "allowing the supplier an unreasonably long time to perform".
- Recommendation: give a range plus a latest date. Say the customer may cancel for a full deposit refund if that date passes.

## 5. Quality and warranty: CPA s55 and s56

**s55(2):** the consumer has a right to goods that:

- "(a) are reasonably suitable for the purposes for which they are generally intended";
- "(b) are of good quality, in good working order and free of any defects";
- "(c) will be useable and durable for a reasonable period of time".

The only exclusions are auctions (s55(1)) and goods the consumer was "expressly informed" were offered "in a specific condition" and agreed to accept (s55(6)).

**s56(2):** "Within six months after the delivery of any goods to a consumer, the consumer may return the goods to the supplier, without penalty and at the supplier's risk and expense, if the goods fail to satisfy the requirements … and the supplier must, at the direction of the consumer, either (a) repair or replace … or (b) refund".

- If a repair fails within three months, the supplier must replace or refund (s56(3)).
- These rights add to any express warranty (s56(4)).
- *Econocom* applied s56(2) to a leather lounge suite that peeled within six months, and ordered a full refund. It also held that a replacement starts a new six-month period ([46]).

**There is no 12-month CPA period for furniture.** "12 months for furniture" can only be DasKasas's own warranty. Re-word the policy so it does not attribute 12 months to the CPA, and fix two conflicts in the draft:

- **Start date.** The CPA clock runs **from delivery**. The draft's "from the date of purchase" shortens it on made-to-order lead times, which matters most for the 6-month decor limit.
- **Assessment fee.** An upfront assessment fee conflicts with "without penalty and at the supplier's risk and expense", even if it is later refunded.

**Special-order goods.** s55 and s56 do not exclude special-order goods. Custom pieces carry the full warranty.

## 6. Online sales: ECTA s42, s43 and s44

**Scope.** ECTA Chapter VII "applies only to electronic transactions" (s42(1)). A "consumer" is "any natural person" who is "the end user" (s1).

**s44, the cooling-off right:**

- "(1) A consumer is entitled to cancel without reason and without penalty any transaction … for the supply (a) of goods within seven days after the date of the receipt of the goods".
- "(2) The only charge that may be levied on the consumer is the direct cost of returning the goods."
- "(3) … the consumer is entitled to a full refund … within 30 days of the date of cancellation."

**s42(2)(f), the exclusion:** "Section 44 does not apply to an electronic transaction … where the goods (i) are made to the consumer's specifications; (ii) are clearly personalised; (iii) by reason of their nature cannot be returned; or (iv) are likely to deteriorate or expire rapidly".

**Does the 7-day cooling-off apply to these made-to-order sales?** Probably not, but this is the weakest point in the analysis.

- The wording is "made to the consumer's specifications". That is narrower than the CPA's "procure … to satisfy the consumer's requirements".
- No South African judgment or tribunal decision on s42(2)(f) was found.
- The same phrase is in EU law. It is defined there as "non-prefabricated goods made on the basis of an individual choice of or decision by the consumer" (Directive 2011/83/EU art 2(4)), with "tailor-made curtains" as the example (recital 49). That is persuasive at most and not binding in South Africa.
- A piece only built once the customer has chosen its fabric fits that definition. If the supplier makes the same item in the same fabric for stock, it does not.

**Exposure if the exclusion fails.** DasKasas would face a 7-day return after delivery with a full refund of deposit and balance, less return transport. Any term excluding s44 rights is "null and void" (s48).

DasKasas's 30-day change-of-mind policy already exceeds s44 for the "standard made-to-order" bucket. The open risk is only the bucket the policy excludes.

**s43 information duties.** The website must show items (a)–(r) of s43(1). These include:

- (h) the main characteristics of the goods;
- (i) the "full price … including transport costs, taxes";
- (k) the terms and guarantees;
- (l) the delivery time;
- (n) "the return, exchange and refund policy";
- (r) "the rights of consumers in terms of section 44, where applicable".

The customer must be able to review, correct and withdraw before ordering (s43(2)). If DasKasas fails these duties, the consumer "may cancel the transaction within 14 days of receiving the goods" (s43(3)). This is a separate escape hatch that the s42 exclusion does **not** switch off.

**Recommendation:** on the product page and at checkout, state that the piece is made to the customer's fabric and colour choice and that the 7-day cooling-off does not apply. Give the lead time and the deposit and forfeiture terms.

## 7. Is deposit-then-balance a lay-by? CPA s62

**s62(1):** "If a supplier agrees to sell particular goods to a consumer, to accept payment for those goods in periodic instalments, and to hold those goods until the consumer has paid the full price for the goods":

- "(a) each amount paid … remains the property of the consumer, and is subject to section 65, until the goods have been delivered";
- "(b) the particular goods remain at the risk of the supplier".

**Consequences if it is a lay-by:**

- **Failure to deliver.** The consumer may choose comparable goods or a refund. The refund is with interest if the failure is beyond the supplier's control, and **"double the amount paid"** otherwise (s62(2)).
- **Penalty cap.** If the consumer terminates, or fails to complete payment "within 60 business days after the anticipated date of completion", the supplier may charge a penalty and must refund the rest (s62(4)). The penalty is allowed only if disclosed in advance (s62(5)(b)), and "may not exceed one percent of the full purchase price" (Reg 34(1)).

**Analysis (no authority found either way):**

- **Points against a lay-by:**
  - "Particular goods" suggests identified goods that already exist and are set aside. A piece not yet made is not "held".
  - One deposit plus one balance on completion is arguably not "periodic instalments".
  - The CPA treats special orders separately (s17(1), s19(5)(b), s47(1)(b)).
  - In *Econocom* a special-order deposit was itself paid in seven monthly instalments of R2,000, and the tribunal did not treat the deal as a lay-by. The point was not argued, so that is weak support.
- **Points for a lay-by:** once the piece is finished and DasKasas holds it pending the balance, all three elements are literally present.

**To keep clear of s62:**

- One deposit and one balance, with no instalment plan.
- The balance due when the piece is ready, and delivery or collection promptly after payment, with no indefinite holding period.
- Call it a special order, not a lay-by.
- Do not offer to "hold" a finished piece while the customer pays it off. That *is* a lay-by.

**This is the first question for a lawyer.**

**VAT has its own lay-by concept.** The VAT Act's "lay-by agreement" (s8(4)) is a different definition. It is tied to a 1980 notice and to goods priced at R10,000 or less. Do not read the CPA and VAT meanings across.

## 8. VAT on deposits: VAT Act s9 and s1

**s9(1):** a supply is "deemed to take place at the time an invoice is issued … or the time any payment of consideration is received by the supplier in respect of that supply, whichever time is earlier".

**s1 "consideration", proviso:** "a deposit (other than a deposit on a returnable container), whether refundable or not, given in respect of a supply of goods or services shall not be considered as payment made for the supply unless and until the supplier applies the deposit as consideration for the supply or such deposit is forfeited".

**SARS VAT 404 (Issue 15), 5.2.1:** "a 'deposit' received that does not form part of the payment due (that is consideration payable) for a supply, will not trigger the time of supply, unless and until, it is applied as payment against the consideration."

**Reading it:**

- A deposit that is a *part-payment of the price* "form[s] part of the payment due". The safe treatment is output VAT in the period it is received.
- Issuing a tax invoice for the full price at order also triggers the full amount.
- A forfeited deposit is consideration when forfeited.

**Lay-by.** A VAT lay-by (≤ R10,000) is supplied only on delivery (s8(4)(a), s9(2)(c)). Amounts kept on cancellation are a deemed supply of services (s8(4)(b)).

**Source caveat.** The current VAT Act text was read from the consolidated Acts Online copy, not a gazette. VAT 404 is SARS guidance, not law. Have the accountant confirm.

## 9. Other points a lawyer would flag

- **Unfair terms (CPA s48, Reg 44).** s48(1) bars supplying "on terms that are unfair, unreasonable or unjust". Reg 44(3) presumes these unfair:
  - "(h) allowing the supplier to increase the price agreed … without giving the consumer the right to terminate". **A price change between deposit and balance needs a right to cancel with a full refund.**
  - "(i) … unilaterally alter … the characteristics of the product", for example substituting fabric.
  - "(p) … an unreasonably long time to perform".
  - "(q) allowing the supplier to retain a payment by the consumer where the latter fails to … perform …, without giving the consumer the right to be compensated in the same amount if the supplier fails".
  - "(r) … damages which significantly exceed the harm suffered".

  Reg 44(2)(a) says the list "is indicative only", so a listed term may still be fair in context.
- **Notice of risky terms (s49).** Terms that "limit in any way the risk or liability of the supplier" or are "an acknowledgement of any fact by the consumer" must be drawn to attention "in a conspicuous manner" before the consumer pays (s49(1), (4)). This covers deposit forfeiture, natural variation in fabric and dye lots, and swatch-colour disclaimers.
- **Conventional Penalties Act 15 of 1962.** Forfeiture clauses are treated as penalty stipulations (s4). If a penalty "is out of proportion to the prejudice suffered by the creditor", a court "may reduce the penalty to such extent as it may consider equitable" (s3). This applies even where s17 does not.
- **Sample and description (CPA s18(3)–(4)).** Goods bought on a description or sample "must in all material respects … correspond". Online swatches and photos set that standard. Disclose natural variation and dye lots up front.
- **Who the CPA protects (s5(2)(b)).** It does not apply where the consumer is a juristic person at or above the Minister's threshold. ECTA Chapter VII protects natural persons only. Trade and corporate orders differ.
- **Peach Payments and card schemes.** No first-party Peach document on pre-orders, deposits or delayed delivery could be retrieved: the Peach merchant-agreement PDFs returned 404. The Peach chargeback guide found only by search is **secondary/unverified**; it says delivery timeframes and refund terms should be clear. Card schemes allow disputes for goods not received, so a long lead time increases chargeback exposure on the deposit. Ask Peach for its rules on deposits and delayed delivery and the chargeback window. Engineering note: the current checkout captures once, so a deposit then a balance means two separate card payments.

## Open questions for a lawyer

1. Is a supplier-made piece, paid as one deposit plus one balance and delivered on payment, outside CPA s62 (lay-by)? Does the answer change if DasKasas holds the finished piece until the balance is paid?
2. Does choosing a fabric and colour from the supplier's standard range make goods "made to the consumer's specifications" under ECTA s42(2)(f)(i)? Is it different if the supplier also makes that combination for stock?
3. Does "belonging to … a consumer" in CPA s65(2) qualify "deposit"? May DasKasas pay the maker from a customer's deposit, or must it keep deposits apart until delivery?
4. What deposit size and forfeiture schedule for special-order goods would survive s48, Reg 44(3)(q) and Conventional Penalties Act s3? For example: refund less admin cost before the maker starts, then up to X% after.
5. For online orders, does ECTA s46(2) carry a refund of the deposit on cancellation for late delivery? How do s46 and CPA s19 interact for an order placed in the showroom but paid online, and for click-and-collect?
6. Can the s55(2)(c) durability right be enforced after the s56(2) six-month window? What should the voluntary 12-month furniture guarantee say so that it does not read as narrowing the CPA, given its start date, assessment fee and "home use only" conditions?
7. Is a price-change clause between deposit and balance acceptable if it gives the customer the right to cancel with a full refund (Reg 44(3)(h))?
8. Do any amendments to the 2011 CPA Regulations after 1 April 2011 affect regs 5, 34 or 44? These were not checked.

## Sources

**Primary sources:**

- Consumer Protection Act 68 of 2008, Government Gazette 32186: https://www.gov.za/sites/default/files/32186_467.pdf. SAFLII consolidation (updated to 13 March 2015, last checked by SAFLII 12 September 2025): https://www.saflii.org/za/legis/consol_act/cpa2008246/
- Consumer Protection Act Regulations, GN R293, Government Gazette 34180 (1 April 2011): https://www.gov.za/sites/default/files/gcis_document/201409/34180rg9515gon293.pdf
- Electronic Communications and Transactions Act 25 of 2002, Government Gazette 23708: https://www.gov.za/sites/default/files/gcis_document/201409/a25-02.pdf. SAFLII consolidation: https://www.saflii.org/za/legis/consol_act/ecata2002427/
- *Adlam v Fabri South Africa (Pty) Ltd* (A5009/2021) [2022] ZAGPJHC 206 (8 April 2022): https://www.saflii.org/za/cases/ZAGPJHC/2022/206.html
- *NCC v Econocom 357 (Pty) Ltd t/a Leather Gallery*, NCT/388029/2025/73(2)(b) (8 June 2025): https://thencc.org.za/wp-content/uploads/2025/08/NCC-v-Econocom-3576-Pty-Ltd-388029.25-final.pdf
- NCC Explanatory Note 4 of 2023 (22 June 2023): https://thencc.org.za/wp-content/uploads/2020/11/Explanatory-note-4-of-2023.pdf
- CGSO Advisory Note 12, *Cancellation of contracts and charging of penalties* [2021] ZACGSO 12: https://www.saflii.org/za/cases/ZACGSO/2021/12.html
- Conventional Penalties Act 15 of 1962: https://www.gov.za/sites/default/files/gcis_document/201505/act-15-1962.pdf
- Value-Added Tax Act 89 of 1991, consolidated text on Acts Online:
  - s1: https://www.acts.co.za/value-added-tax-act-1991/1__definitions
  - s8: https://www.acts.co.za/value-added-tax-act-1991/8__certain_supplies_of_goods_or_services_deemed_to_be_made_or_not_made
  - s9: https://www.acts.co.za/value-added-tax-act-1991/9__time_of_supply
- SARS VAT 404 *Guide for Vendors*, Issue 15: https://www.sars.gov.za/legal-pub-guide-vat404-vat-404-guide-for-vendors

**Comparative and secondary sources:**

- Directive 2011/83/EU, art 2(4) and recital 49 (comparative only): https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32011L0083
- Naudé & Eiselen, *Commentary on the Consumer Protection Act*, as cited by counsel in *Adlam* [39] (secondary, not read).
