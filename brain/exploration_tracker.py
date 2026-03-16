import allure


class ExplorationTracker:

    def __init__(self):
        self.steps = []

    def add(self, action, url):

        step = f"{len(self.steps)+1}. {action} → {url}"

        self.steps.append(step)

    def attach_report(self):

        if not self.steps:
            return

        timeline = "\n".join(self.steps)

        allure.attach(
            timeline,
            name="AI Exploration Timeline",
            attachment_type=allure.attachment_type.TEXT
        )