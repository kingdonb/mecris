import re

with open("services/reminder_service.py", "r") as f:
    content = f.read()

# Replace the block for the arabic else condition
# "logger.info(f"Language reminder suppressed by dynamic cooldown...)"
# Add return

content = content.replace("""                else:
                    logger.info(f"Language reminder suppressed by dynamic cooldown ({hours_since_arabic:.1f}h < {dynamic_arabic_cooldown:.1f}h)")""", 
"""                else:
                    logger.info(f"Language reminder suppressed by dynamic cooldown ({hours_since_arabic:.1f}h < {dynamic_arabic_cooldown:.1f}h)")
                    return {"should_send": False, "reason": f"Arabic review reminder on cooldown ({hours_since_arabic:.1f}h since last)"}""")

content = content.replace("""                            else:
                                logger.info(f"Arabic escalation suppressed by cooldown ({hours_since_escalation:.1f}h since last)")""",
"""                            else:
                                logger.info(f"Arabic escalation suppressed by cooldown ({hours_since_escalation:.1f}h since last)")
                                return {"should_send": False, "reason": f"Arabic escalation on cooldown ({hours_since_escalation:.1f}h since last)"}""")

content = content.replace('return {"should_send": False, "reason": f"Normal sleep window active (8pm-8am, current hour: {current_hour})"}',
                          'return {"should_send": False, "reason": f"Sleep window active (8pm-8am, current hour: {current_hour})"}')

with open("services/reminder_service.py", "w") as f:
    f.write(content)
print("Patched 2 successfully")
