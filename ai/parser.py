def parse_ai_action(ai_output):

    action = None
    target = None

    for line in ai_output.split("\n"):

        if "ACTION:" in line:
            action = line.split(":")[1].strip()

        if "TARGET:" in line:
            target = line.split(":")[1].strip()

    return action, target