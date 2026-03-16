def validate_target(page, target):

    locator = page.locator(f"text={target}")

    return locator.count() > 0