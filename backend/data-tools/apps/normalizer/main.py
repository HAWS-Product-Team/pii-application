import pdfplumber
import re
from datetime import datetime
import csv

def main():
    file_name = "FILE_NAME"

    def extract_total(line: str):
        match = re.search(r"\$[\d,]+\.\d{2}", line)
        return match.group() if match else None

    def extract_order_placed_date(lines, index, line):
        date_pattern = r"\w+ \d{1,2}, \d{4}"
        search_date = re.search(date_pattern, line)
        if not search_date and index + 1 < len(lines):
            search_date = re.search(date_pattern, lines[index + 1])
        if search_date:
            return datetime.strftime(datetime.strptime(search_date.group(), "%B %d, %Y").date(), "%d/%m/%Y")
        return None

    def capture_item_name(lines, start_index):
        ignore_phrases = [
            "YOUR PACKAGE WAS LEFT",
            "VIEW INVOICE",
            "GET PRODUCT SUPPORT",
            "ASK PRODUCT QUESTION",
            "DELIVERED",
            "HANDED TO",
            "MAILBOX",
            "FRONT DOOR",
            "PORCH",
            "RECEIVED BY"
        ]
        footer_keywords = [
            "LEAVE SELLER FEEDBACK",
            "WRITE A PRODUCT REVIEW",
            "RETURN WINDOW CLOSED"
        ]

        item_lines = []
        for line in lines[start_index:]:
            line = line.strip()
            if any(keyword in line.upper() for keyword in footer_keywords):
                break
            if any(phrase in line.upper() for phrase in ignore_phrases):
                continue
            if len(line) < 3:
                continue
            item_lines.append(line)
        return " ".join(item_lines)

    orders = []

    with pdfplumber.open(file_name) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split("\n")
            
            current_order_date = None
            current_total = None
            index = 0

            while index < len(lines):
                line = lines[index].strip()

                # Extract Order Placed date
                if "ORDER PLACED" in line.upper():
                    date = extract_order_placed_date(lines, index, line)
                    if date:
                        current_order_date = date

                # Extract total from ANY line with a dollar amount
                total = extract_total(line)
                if total:
                    current_total = total

                # Capture product name after "Delivered"
                if "DELIVERED" in line.upper():
                    item_name = capture_item_name(lines, index + 1)
                    if item_name:
                        orders.append([
                            current_order_date if current_order_date else "N/A",
                            current_total if current_total else "N/A",
                            item_name
                        ])
                        # reset for next order
                        current_order_date = None
                        current_total = None
                    # Skip captured lines to avoid duplicates
                    index += len(item_name.split("\n"))  # approximate
                index += 1

        # --- Write to CSV ---
        with open("amazon_orders.csv", "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Order Date", "Total", "Item Name"])
            writer.writerows(orders)

        print("CSV saved as amazon_orders.csv")

if __name__ == "__main__":
    main()
