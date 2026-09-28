import re

with open('src/pages/Home/Home.module.css', 'r') as f:
    content = f.read()

# First replace heroActions inside @media (max-width: 768px)
# Since there are multiple occurrences of `.heroActions`, we want the one in the 768px block which is around line 1453
# Currently it looks like:
#   .heroActions {
#     margin-top: 0.5rem;
#     display: grid;
#   }
# We want to change to:
#   .heroActions {
#     margin-top: 0;
#     gap: 0.75rem;
#     display: grid;
#   }

old_actions = """  .heroActions {
    margin-top: 0.5rem;
    display: grid;
  }"""
new_actions = """  .heroActions {
    margin-top: 0;
    gap: 0.75rem;
    display: grid;
  }"""

if old_actions in content:
    content = content.replace(old_actions, new_actions)
    print("Replaced .heroActions")
else:
    print("Could not find exact .heroActions string")

# Now replace heroWhatsapp in the same block which is currently:
#   .heroWhatsapp {
#     margin-bottom: 5.5rem;
#     position: relative;
#     z-index: 91;
#   }
# We want to add margin-top: 0.5rem

old_whatsapp = """  .heroWhatsapp {
    margin-bottom: 5.5rem;
    position: relative;
    z-index: 91;
  }"""
new_whatsapp = """  .heroWhatsapp {
    margin-top: 0.5rem;
    margin-bottom: 5.5rem;
    position: relative;
    z-index: 91;
  }"""

if old_whatsapp in content:
    content = content.replace(old_whatsapp, new_whatsapp)
    print("Replaced .heroWhatsapp")
else:
    print("Could not find exact .heroWhatsapp string")

with open('src/pages/Home/Home.module.css', 'w') as f:
    f.write(content)
