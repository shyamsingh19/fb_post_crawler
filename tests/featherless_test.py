import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=os.getenv("CRAWLER_API_KEY"),
)

text = """
🏠 FLATMATE REQUIRED – 2BHK | KONDAPUR / NEW HAFEEZPET 🏠
Looking for a flatmate (Male/Female) to share a spacious semi-furnished 2BHK in Kondapur / New Hafeezpet.
📅 Available from: 31st August
🐾 Pet-friendly flat
🥗 Pure vegetarian household – eggs allowed
📍 Location: Kondapur – New Hafeezpet area
🏋️ Gym nearby | 🛍️ Mall nearby | 🛣️ Close to main road | 🏸 Sports center nearby | opposite to genpect | opposite to D mart
🚗 Dedicated two wheeler parking available
🛏️ Room & Flat Details
• Personal bathroom just outside the room
• Geyser installed in the bathroom
• Almost fully furnished setup
• Bed & AC are not available in the room
🏠 Flat Amenities
• Sofa
• 55-inch TV
• Washing machine
• Fridge
• Completely set-up kitchen
• Microwave
• Griller
• Air fryer
• Shoe rack
• Wardrobe
• And other essentials
💰 Rent: ₹13,000/month (including maintenance)
💵 Brokerage: ₹6,500 – recoverable from the next tenant
💰 Setup cost: ₹10,000 – includes fridge, washing machine, sofa & TV
✨ The flat is almost completely set up, so you can move in without having to arrange most of the essentials.
👨👩 Male / Female both welcome!
🐶🐱 Pet-friendly
🥚 Vegetarian household – eggs allowed
📩 Interested? DM me for photos, exact location and more details.
9993956552.
"""

response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V3-0324",
    messages=[
        {
            "role": "system",
            "content": "Extract structured details (rent, location, contact) as JSON from rental posts.",
        },
        {
            "role": "user",
            "content": text,
        },
    ],
)

print(response.choices[0].message.content)
