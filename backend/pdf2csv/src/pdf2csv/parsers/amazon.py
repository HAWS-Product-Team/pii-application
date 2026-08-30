"""Amazon Order History PDF parser."""

import re
from datetime import UTC, datetime

from pdf2csv.models import Record
from pdf2csv.parsers.base import BaseParser

# Delivery / navigation lines to ignore inside an order block
DELIVERY_PATTERNS = [
    r"^Delivered\b",
    r"^Your package was",
    r"^Package was",
    r"^Arriving\b",
    r"^Out for delivery\b",
    r"^Ask Alexa",
    r"^View order details",
    r"^View invoice",
    r"^Search all orders",
    r"^Review the details",
    r"^An item you have purchased has been recalled",
    r"^\d+\s+orders placed in",
    r"^›",
    r"^Your Orders",
    r"^Your Account",
    r"^Orders Buy Again",
    r"^Submit",
    r"^All\b",
    r"^Go Returns",
    r"^& Orders Cart",
    r"^Hello,",
    r"^\d+Search Amazon",
    r"^Search Amazon",
    r"^Account & Lists",
    r"^Archive order",
    r"^Cancel items",
    r"^Change payment method",
    r"^Problem with order",
    r"^Track package",
    r"^Ask Product Question",
    r"^View your Subscribe & Save",
    r"^View return/refund status",
    r"^When will I get my refund\?",
    r"^Why is a refund being issued\?",
]

# Patterns that mark the start of page footer / browsing recommendations
FOOTER_PATTERNS = [
    r"^←Previous",
    r"^\bPrevious\b.*\bNext\b",
    r"^Customers who viewed",
    r"^discounts\s+Customers",
    r"^Shopping for work",
    r"^Save with business",
    r"^Create a free business",
    r"^Related to items",
    r"^Page \d+ of \d+",
    r"^Your Account\s+›",
    r"^Conditions of Use",
    r"^Privacy Notice",
    r"^Interest-Based Ads",
    r"^©\s*\d{4}",
]

# Button and action line patterns that separate items
ACTION_PATTERNS = [
    r"^Buy it again",
    r"^Write a product review",
    r"^Get product support",
    r"^Track package",
    r"^Add a protection plan",
    r"^More options",
    r"^Problem with order",
    r"^View your item",
    r"^Archive order",
    r"^Cancel items",
    r"^Change payment method",
    r"^Share gift receipt",
    r"^Leave seller feedback",
    r"^Leave delivery feedback",
    r"^Return or replace items",
    r"^Return items",
    r"^Return window closed",
    r"^Return eligible",
    r"^Auto-delivered:",
    r"^Item recalled",
    r"^Safety alert",
    r"^Not yet shipped",
    r"^Ask Product Question",
    r"^View your Subscribe & Save",
    r"^View return/refund status",
]

# Trailing metadata to strip from item descriptions
TRAILING_STRIP_REGEX = [
    r"Return window closed on.*$",
    r"Return or replace items: Eligible through.*$",
    r"Return or replace items.*$",
    r"Return eligible through.*$",
    r"Return items:.*$",
    r"Return items.*$",
    r"Auto-delivered:.*$",
    r"Eligible through.*$",
    r"Buy it again.*$",
    r"View return/refund status.*$",
    r"Ask Product Question.*$",
]

# Non-description prefixes to strip from item descriptions
PREFIX_STRIP_REGEX = [
    r"^An item you have purchased has been recalled or has a safety alert\s*",
    r"^Refund issued\s+A refund will appear on your original payment method in [^.]+\.\s*(Why is a refund being issued\?)?\s*",
    r"^Refunded\s+There's no need to return your item\.\s*Your refund has been issued\.\s*(When will I get my refund\?)?\s*",
]


# Refund markers that trigger dropping the entire order
REFUND_PATTERNS = [
    r"Refund issued",
    r"\bRefunded\b",
    r"A refund will appear on your original payment method",
    r"Your refund has been issued",
]


def clean_description_text(desc: str) -> str:
    """Strip known prefixes and trailing metadata from an item description."""
    cleaned = desc.strip()
    for p_pat in PREFIX_STRIP_REGEX:
        cleaned = re.sub(p_pat, "", cleaned, flags=re.IGNORECASE).strip()
    for t_pat in TRAILING_STRIP_REGEX:
        cleaned = re.sub(t_pat, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def parse_date_str(date_str: str) -> str:
    """Convert human-readable date string into ISO YYYY-MM-DD format."""
    cleaned = date_str.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned


def parse_amount_str(amount_str: str) -> str:
    """Format total amount string as numeric string with 2 decimal places."""
    cleaned = amount_str.replace("$", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return f"{val:.2f}"
    except ValueError:
        return cleaned


class AmazonOrderHistoryParser(BaseParser):
    """Parser for Amazon Order History PDF statements."""

    def parse(self, lines: list[str]) -> list[Record]:
        """Parse extracted lines into Record objects."""
        orders_info = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Check single-line anchor format:
            # Line 1: ORDER PLACED ... TOTAL ... ORDER # <id>
            # Line 2: <Month D, YYYY> $<Amount> ...
            m_hdr = re.search(r"ORDER PLACED.*TOTAL.*ORDER #\s*([\d-]+)", line, re.IGNORECASE)
            if m_hdr and i + 1 < len(lines):
                val_line = lines[i + 1].strip()
                m_val = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})\s+\$([\d,]+\.\d{2})", val_line)
                if m_val:
                    orders_info.append(
                        {
                            "start_idx": i,
                            "content_start_idx": i + 2,
                            "order_num": m_hdr.group(1),
                            "date_str": m_val.group(1),
                            "total_str": m_val.group(2),
                        }
                    )
                    i += 2
                    continue

            # Check multi-line anchor format:
            # Line: ORDER PLACED
            # Following lines contain Date, TOTAL, Amount, ORDER #
            if line.upper() == "ORDER PLACED":
                j = i + 1
                order_data = {}
                while j < min(len(lines), i + 15):
                    cur = lines[j].strip()
                    if cur.upper() == "ORDER PLACED":
                        break
                    m_date = re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$", cur)
                    if m_date and "date" not in order_data:
                        order_data["date"] = cur
                    elif cur.upper() == "TOTAL" and j + 1 < len(lines):
                        m_tot = re.match(r"^\$([\d,]+\.\d{2})$", lines[j + 1].strip())
                        if m_tot:
                            order_data["total"] = m_tot.group(1)
                            j += 1
                    elif "ORDER #" in cur.upper():
                        m_ord = re.search(r"ORDER #\s*([\d-]+)", cur, re.IGNORECASE)
                        if m_ord:
                            order_data["order_num"] = m_ord.group(1)
                            j += 1
                            break
                    j += 1

                if "date" in order_data and "total" in order_data and "order_num" in order_data:
                    orders_info.append(
                        {
                            "start_idx": i,
                            "content_start_idx": j,
                            "order_num": order_data["order_num"],
                            "date_str": order_data["date"],
                            "total_str": order_data["total"],
                        }
                    )
                    i = j
                    continue

            i += 1

        records: list[Record] = []
        for idx, ord_info in enumerate(orders_info):
            content_start = ord_info["content_start_idx"]
            is_last_order = idx + 1 == len(orders_info)
            content_end = orders_info[idx + 1]["start_idx"] if not is_last_order else len(lines)
            order_lines = lines[content_start:content_end]

            # Section 6.5: Drop entire order if it carries a refund/credit marker
            if any(
                any(re.search(pat, l_str, re.IGNORECASE) for pat in REFUND_PATTERNS)
                for l_str in order_lines
            ):
                continue

            items: list[str] = []
            cur_item_parts: list[str] = []
            seen_delivery_in_last = False

            for raw_line in order_lines:
                l_str = raw_line.strip()
                if not l_str:
                    continue

                if any(re.search(pat, l_str, re.IGNORECASE) for pat in FOOTER_PATTERNS):
                    break

                # Section 6.6: Header-less orphan blocks in the trailing order section
                if is_last_order and re.search(r"^Delivered\b", l_str, re.IGNORECASE):
                    if seen_delivery_in_last:
                        break
                    seen_delivery_in_last = True
                    continue

                if any(re.search(pat, l_str, re.IGNORECASE) for pat in DELIVERY_PATTERNS):
                    continue

                # Standalone integer badge line is ignored (Section 6.4)
                if re.match(r"^\d+$", l_str):
                    continue

                # Action button / metadata line ends current item description
                if any(re.search(pat, l_str, re.IGNORECASE) for pat in ACTION_PATTERNS):
                    if cur_item_parts:
                        desc = clean_description_text(" ".join(cur_item_parts))
                        if desc:
                            items.append(desc)
                        cur_item_parts = []
                    continue

                cur_item_parts.append(l_str)

            if cur_item_parts:
                desc = clean_description_text(" ".join(cur_item_parts))
                if desc:
                    items.append(desc)

            clean_items = []
            for itm in items:
                cleaned = clean_description_text(itm)
                if cleaned and not any(
                    re.search(pat, cleaned, re.IGNORECASE) for pat in DELIVERY_PATTERNS
                ):
                    clean_items.append(cleaned)

            iso_date = parse_date_str(ord_info["date_str"])
            total_float_str = parse_amount_str(ord_info["total_str"])
            try:
                total_val = float(total_float_str)
            except ValueError:
                total_val = 0.0

            n_items = len(clean_items)
            if n_items == 0:
                # Valid order header/total but zero extractable descriptions (Section 6.4)
                price_str = f"{total_val:.2f}"
                records.append(
                    Record(
                        date=iso_date,
                        item_description="",
                        quantity=1,
                        unit_price=price_str,
                        total_price=price_str,
                    )
                )
            else:
                # Even-split rounding rule (Section 6.3)
                total_cents = round(total_val * 100)
                base_cents = total_cents // n_items
                remainder = total_cents - (base_cents * n_items)

                for item_idx, desc in enumerate(clean_items):
                    item_cents = base_cents + 1 if item_idx < remainder else base_cents
                    price_str = f"{item_cents / 100:.2f}"
                    records.append(
                        Record(
                            date=iso_date,
                            item_description=desc,
                            quantity=1,
                            unit_price=price_str,
                            total_price=price_str,
                        )
                    )

        return records
