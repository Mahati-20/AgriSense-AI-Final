"""Offline, rule-based farming answers for the AgriSense Assistant.

This module has no network, model, database, or API-key dependencies. Knowledge
is intentionally general; regional schedules and exact input rates must come
from a current local agricultural advisory or soil test.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any


SOURCES = {
    "icar_crop_advisory": {
        "name": "ICAR Kharif Agro-Advisory for Farmers 2025",
        "url": "https://icar.gov.in/en/icar-kharif-agro-advisories-farmers-2025-1",
    },
    "icar_ipm": {
        "name": "ICAR: Integrated Pest Management",
        "url": "https://www.icar.gov.in/en/integrated-pest-management-sustainable-approach-responsible-pest-management",
    },
    "icar_kvk": {
        "name": "ICAR: Krishi Vigyan Kendras",
        "url": "https://www.icar.gov.in/en/krishi-vigyan-kendras-kvks",
    },
    "fao_ffs": {
        "name": "FAO Farmer Field School approach",
        "url": "https://www.fao.org/pest-and-pesticide-management/pesticide-risk-reduction/ffs/en/",
    },
    "icar_crop_science": {
        "name": "ICAR Crop Science",
        "url": "https://www.icar.gov.in/en/crop-science/crop-science",
    },
}


# Each profile gives cautious, broadly applicable pointers, not a local crop
# calendar or a substitute for a variety-specific production package.
CROP_PROFILES: dict[str, dict[str, str]] = {
    "tomato": {"aliases": "tomato tomatoes tamatar", "care": "Use a locally suitable variety, support indeterminate plants, keep soil moisture reasonably even, and avoid prolonged leaf wetness. Training and pruning depend on variety and production system.", "harvest": "Harvest at the maturity stage suited to use and transport; color stage varies by variety and destination. Handle gently and keep produce shaded."},
    "potato": {"aliases": "potato potatoes aloo", "care": "Use healthy seed tubers, maintain drainage, and hill soil around developing tubers so they are not exposed to light. Water and nutrient needs vary with soil and growth stage.", "harvest": "Harvest after the crop has matured and the skin is set for the intended use. Avoid harvesting very wet soil where possible; cure and store only in a suitable, ventilated place."},
    "onion": {"aliases": "onion onions pyaz", "care": "Onion roots are relatively shallow, so avoid long dry spells during active growth while preventing waterlogging. Keep weeds from competing early in the season.", "harvest": "Maturity is indicated by neck softening and tops falling in many bulb onions. Cure bulbs in a dry, ventilated, shaded place; timing varies by cultivar and climate."},
    "chilli": {"aliases": "chilli chillies chili chilies pepper mirchi", "care": "Use clean planting material, good drainage, and regular moisture without waterlogging. Monitor leaves and fruits frequently; local pest pressure and suitable varieties vary greatly.", "harvest": "Pick green or ripe fruits according to the variety and intended market. Harvest regularly and handle gently; color alone may not establish quality or safe maturity."},
    "brinjal": {"aliases": "brinjal eggplant aubergine baingan", "care": "Choose a locally adapted variety, maintain drainage and steady moisture, and inspect shoots and fruits regularly for damage. Remove badly infested plant parts safely.", "harvest": "Many varieties are picked while fruits are glossy and firm, before seeds become hard; the right stage depends on variety and use."},
    "okra": {"aliases": "okra lady finger ladyfinger bhindi bhendi", "care": "Warm conditions and a well-drained root zone suit okra; avoid prolonged waterlogging and keep the crop weed-free while young.", "harvest": "Pick pods frequently while tender. Older pods become fibrous; use the variety and market standard to judge picking size."},
    "cucumber": {"aliases": "cucumber cucumbers kheera", "care": "Provide drainage and even moisture during flowering and fruit development. Trellising can improve access and fruit cleanliness where the variety and system suit it.", "harvest": "Harvest firm fruits at the size and maturity preferred for the variety and market; overmature fruits can reduce continued production."},
    "beans": {"aliases": "bean beans french bean french beans green bean green beans", "care": "Select bush or climbing types suited to the site; support climbing types and maintain drainage. Avoid working among wet plants when disease is a concern.", "harvest": "For fresh use, harvest pods while tender and before seeds become overly prominent. Picking frequency depends on type and weather."},
    "peas": {"aliases": "pea peas garden pea", "care": "Peas generally perform best in cool, suitable local planting windows. Provide support to climbing types and avoid waterlogged soil; exact season varies by region.", "harvest": "Pick green pods when filled but still tender for fresh use. Dry-seed harvest requires full maturity and careful drying."},
    "cabbage": {"aliases": "cabbage cabbages", "care": "Use a locally adapted variety and maintain even moisture during head formation. Inspect regularly for caterpillars and other pests; do not assume every hole is caused by the same pest.", "harvest": "Harvest when heads are firm and appropriately sized for the variety and market, before splitting or deterioration."},
    "cauliflower": {"aliases": "cauliflower cauliflowers gobhi", "care": "Choose a variety suited to the local season because curd development is sensitive to temperature. Maintain even soil moisture and protect developing curds according to local practice.", "harvest": "Cut compact, firm curds before they loosen or discolor. Maturity timing varies by variety and temperature."},
    "spinach": {"aliases": "spinach palak", "care": "Maintain a moist but well-drained seedbed and keep young plants free of weeds. Heat and long days can affect leaf quality and bolting depending on variety.", "harvest": "Harvest outer leaves or the whole plant at the desired tender stage; wash and cool promptly after harvest."},
    "lettuce": {"aliases": "lettuce", "care": "Use a locally suitable variety and avoid heat and moisture stress where possible; lettuce quality is strongly affected by temperature and variety.", "harvest": "Harvest leaves or heads at the intended market stage before excessive bolting or bitterness; timing differs by type."},
    "bitter gourd": {"aliases": "bitter gourd bitter melon karela", "care": "Provide a trellis where practical, maintain drainage, and support pollination and even moisture. Inspect vines and fruit regularly for pest damage.", "harvest": "Harvest fruits at the preferred immature-green stage for the variety and market; frequent picking helps avoid overmaturity."},
    "bottle gourd": {"aliases": "bottle gourd lauki", "care": "Provide space or a suitable trellis, good drainage, and even moisture during flowering and fruit growth. Protect young plants from weeds and physical damage.", "harvest": "Harvest while fruits are tender and before the rind hardens, using the variety and intended use as the guide."},
    "ridge gourd": {"aliases": "ridge gourd turai luffa", "care": "Support climbing vines where possible and keep the root zone moist but not waterlogged. Inspect flowers and young fruits as the crop develops.", "harvest": "Pick fruits young and tender before fibers become prominent; picking stage depends on variety and use."},
    "pumpkin": {"aliases": "pumpkin pumpkins squash", "care": "Allow adequate vine space, maintain drainage, and avoid moisture stress during establishment and fruit growth. Protect mature fruit from injury and wet ground where feasible.", "harvest": "Harvest at mature rind and stem condition appropriate to the cultivar; cure and storage needs vary among types."},
    "carrot": {"aliases": "carrot carrots gajar", "care": "A loose, stone-free seedbed helps roots develop evenly. Keep moisture reasonably even during germination and root formation; soil and cultivar affect shape and maturity.", "harvest": "Harvest roots when they reach the preferred size and tenderness for the variety and market."},
    "mango": {"aliases": "mango mangoes mangos aam", "care": "Use locally recommended cultivars and maintain drainage. Flowering, fruit set, pruning, and pest advice are strongly seasonal and regional; avoid applying inputs without a local recommendation.", "harvest": "Maturity indices differ by cultivar and destination. Use local harvest guidance and handle fruit carefully; skin color alone may not indicate maturity."},
    "banana": {"aliases": "banana bananas kela plantain", "care": "Maintain a well-drained root zone and steady moisture; wind exposure, cultivar, and production system affect support and sucker management.", "harvest": "Harvest timing depends on cultivar and market distance. Filled fingers and local maturity guidance are more useful than a fixed calendar date."},
    "papaya": {"aliases": "papaya papayas", "care": "Prevent waterlogging around the stem and protect plants from wind and injury. Variety, sex type, and local disease pressure affect management.", "harvest": "Harvest maturity depends on whether fruit is for nearby use or transport; use cultivar-specific color-break and firmness guidance."},
    "guava": {"aliases": "guava guavas amrood", "care": "Maintain drainage and monitor flushes, flowers, and fruit for pest or disease signs. Pruning and crop-season management vary by region and production goal.", "harvest": "Use cultivar-specific size, firmness, aroma, and color cues. Handle ripe fruit gently to limit bruising."},
    "citrus": {"aliases": "citrus orange oranges lemon lemons lime limes mosambi mandarin", "care": "Good drainage is important; avoid prolonged waterlogging around roots. Identify the citrus type and check soil or leaf tests before correcting suspected nutrient problems.", "harvest": "Citrus maturity depends on species, cultivar, acidity, and destination; peel color alone can be misleading."},
    "grapes": {"aliases": "grape grapes vineyard", "care": "Use a locally adapted cultivar and trained support system. Pruning, canopy management, irrigation, and disease prevention are highly region- and season-specific.", "harvest": "Harvest maturity depends on cultivar and use. Where available, combine local guidance with taste and measured maturity indicators rather than color alone."},
    "watermelon": {"aliases": "watermelon watermelons", "care": "Provide a warm, well-drained site and avoid large moisture swings during fruit growth. Pollination, cultivar, and weather affect fruit set and quality.", "harvest": "Maturity signs vary by cultivar and are not perfectly reliable in isolation. Check multiple locally recommended indicators and avoid claiming maturity from one sign."},
    "muskmelon": {"aliases": "muskmelon muskmelons cantaloupe kharbuja", "care": "Use a well-drained site and steady moisture while fruit is developing; reduce unnecessary wetting of foliage and fruit where practical.", "harvest": "Use cultivar-specific maturity cues such as aroma, rind change, and fruit separation; no single sign applies to all types."},
    "pomegranate": {"aliases": "pomegranate pomegranates anar", "care": "Maintain drainage and avoid abrupt moisture changes during fruit growth where possible, as stress can contribute to fruit quality problems. Pruning and pest management are local decisions.", "harvest": "Use cultivar-specific maturity and sound cues. Harvest carefully to reduce cracking and bruising; color alone is not sufficient."},
    "apple": {"aliases": "apple apples", "care": "Cultivar choice depends on local climate, especially winter chilling and elevation. Use local horticultural guidance for pollination, pruning, irrigation, and disease management.", "harvest": "Maturity is cultivar-specific. Use local maturity indices and intended storage or transport needs rather than a fixed date."},
    "coconut": {"aliases": "coconut coconuts", "care": "Water and nutrient management depend on rainfall, soil, palm age, and intercrops. Maintain a clean, drained basin and use local recommendations for inputs.", "harvest": "Harvest interval and maturity depend on whether tender nuts or mature nuts are wanted; follow the use and cultivar."},
    "pineapple": {"aliases": "pineapple pineapples ananas", "care": "Use healthy planting material and well-drained soil. Planting density, flowering management, and maturity depend on production system and local recommendations.", "harvest": "Harvest maturity depends on cultivar and distance to market; use local external-color and internal-quality guidance."},
    "rice": {"aliases": "rice paddy dhan", "care": "Choose a variety and establishment method suited to local rainfall, soil, and water availability. Water management differs among transplanted, direct-seeded, irrigated, and rain-fed systems; do not assume continuous flooding is appropriate everywhere.", "harvest": "Use locally recommended grain-maturity cues and harvest before excessive shattering or weather damage. Dry grain safely before storage."},
    "wheat": {"aliases": "wheat gehun", "care": "Sowing window and variety are region-specific. Use healthy seed, prepare a suitable seedbed, and manage irrigation according to crop stage, soil, and rainfall.", "harvest": "Harvest when the crop and grain reach locally recommended maturity. Dry grain to safe storage moisture and protect it from pests."},
    "maize": {"aliases": "maize corn makka", "care": "Select a variety suited to the season and purpose. Establish a uniform stand, control early weed competition, and avoid moisture stress around flowering where possible.", "harvest": "Harvest stage depends on whether maize is for green cobs, fodder, or dry grain. Dry grain adequately before storage."},
    "millets": {"aliases": "millet millets ragi finger millet bajra pearl millet jowar sorghum", "care": "Use a locally adapted millet and sowing window. Many millet systems are suited to dryland conditions, but drought tolerance does not remove the need for suitable establishment and soil moisture.", "harvest": "Harvest when panicles or heads reach crop-specific maturity. Dry grain thoroughly and store cleanly."},
    "pulses": {"aliases": "pulse pulses legume legumes chickpea gram chana pigeon pea tur arhar lentil masoor mung moong urad black gram cowpea", "care": "Pulse crops differ widely; choose crop-specific seed and local sowing guidance. Avoid waterlogging, monitor pests, and use locally recommended inoculants or nutrient practices where appropriate.", "harvest": "Harvest at crop-specific pod maturity. Some pulses shatter when over-dry, so use local timing and dry harvested material safely."},
    "groundnut": {"aliases": "groundnut peanut peanuts moongphali", "care": "A friable, well-drained soil supports pegging and pod development. Avoid waterlogging and follow local nutrient and disease advice.", "harvest": "Check pod maturity using local guidance before lifting. Dry pods thoroughly and protect them from moisture and contamination."},
    "cotton": {"aliases": "cotton kapas", "care": "Use locally recommended varieties and monitor the field regularly for pests and beneficial insects. Integrated pest management and local thresholds matter; do not spray by calendar alone.", "harvest": "Pick fully opened, dry bolls and keep seed cotton clean. Follow local advice on repeated picking and safe storage."},
    "sugarcane": {"aliases": "sugarcane sugar cane ganna", "care": "Variety, planting time, irrigation, and ratoon management are region-specific. Keep drainage adequate and use locally recommended planting material and nutrient plans.", "harvest": "Harvest timing depends on variety, maturity, and mill or jaggery use. Follow local maturity and transport guidance rather than a universal calendar."},
    "soybean": {"aliases": "soybean soybeans soya", "care": "Use certified, locally adapted seed and suitable sowing conditions. Ensure drainage and monitor weeds and pests early; regional package-of-practice guidance is important.", "harvest": "Harvest when pods and plants reach locally recommended maturity, avoiding delays that increase shattering or weather exposure."},
    "mustard": {"aliases": "mustard rapeseed sarson", "care": "Choose a variety and sowing window suited to the region. Establish a healthy stand, manage weeds early, and monitor flowering crops for locally important pests.", "harvest": "Harvest when pods reach crop-specific maturity, before excessive shattering. Dry seed safely before storage."},
}


INTENTS: dict[str, dict[str, Any]] = {
    "project": {"patterns": [r"\bagrisense\b", r"\bhackathon\b", r"\bjudge\b", r"\bhow does (the )?assistant work\b", r"\brule[- ]based\b", r"\bwithout (gemini|groq|generative|ai model)\b", r"\bwhich apis?\b", r"\bwhat (is|does) (this|the) (project|app|assistant)\b", r"\blimitations?\b", r"\bmachine learning\b", r"\b(problem|intended users?|target users?|who uses)\b.{0,30}\b(agrisense|app|project|assistant|farmer)s?\b", r"\bhow (does|do) (the )?(assistant|system) (choose|select|match)\b"], "source": "project"},
    "live_market": {"patterns": [r"\b(today|current|currently|latest|live|right now)\b.{0,35}\b(price|market|mandi|rate)s?\b", r"\b(price|market|mandi|rate)s?\b.{0,35}\b(today|current|latest|live)\b", r"\b(market price|mandi rate|price of|price for)\b"], "source": None},
    "live_weather": {"patterns": [r"\b(today|current|currently|latest|live|right now|forecast)\b.{0,35}\b(weather|rain|temperature|humidity)\b", r"\b(weather|rain|temperature|humidity)\b.{0,35}\b(today|current|forecast)\b", r"\bwill it rain\b", r"\b(weather in|rain forecast)\b"], "source": None},
    "farm_records": {"patterns": [r"\b(my|our|saved|recorded)\b.{0,35}\b(records?|farm records?|crop records?|harvests?|tasks?|profits?|plantings?|fields?)\b", r"\b(what|show|list|summarize|review|compare)\b.{0,20}\b(my|our)\b.{0,20}\b(farm|crop|harvest|task|profit|planting|field)s?\b", r"\bwhat (do|does) (my|our) records show\b"], "source": "farm"},
    "economics": {"patterns": [r"\b(break.?even|profit|revenue|cost[- ]benefit|cost per|input cost|farm economics|gross margin)\b", r"\bcalculate\b.{0,20}\b(cost|profit|revenue|yield)\b"], "source": None},
    "harvest": {"patterns": [r"\b(harvest|harvesting|maturity|mature|ready to pick|when to pick|picking time)\b", r"\bwhen (can|should|do) i (pick|harvest)\b"], "source": "crop"},
    "storage": {"patterns": [r"\b(store|storage|post.?harvest|shelf life|preserve|spoila?ge|packaging|grading|sorting|transport)\b"], "source": "icar_crop_advisory"},
    "yellowing": {"patterns": [r"\b(yellow|yellowing|chlorosis)\b.{0,40}\b(leaf|leaves|plant|crop)s?\b", r"\b(leaf|leaves|plant|crop)s?\b.{0,40}\b(yellow|yellowing|chlorosis)\b"], "source": "icar_ipm"},
    "wilting": {"patterns": [r"\b(wilt|wilting|drooping|limp)\b"], "source": "icar_ipm"},
    "leaf_curl": {"patterns": [r"\b(leaf|leaves)\b.{0,20}\b(curl|curling|rolled|twisted)\b", r"\b(curl|curling|rolled|twisted)\b.{0,20}\b(leaf|leaves)\b"], "source": "icar_ipm"},
    "leaf_spots": {"patterns": [r"\b(leaf|leaves|plant)s?\b.{0,20}\b(spot|spots|blight|mildew|lesion)s?\b", r"\b(spot|spots|blight|mildew|lesion)s?\b.{0,20}\b(leaf|leaves|plant)s?\b", r"\bspots? on (my )?(plant|leaves|fruit)\b"], "source": "icar_ipm"},
    "leaf_discoloration": {"patterns": [r"\b(brown|black|pale)\b.{0,25}\b(leaf|leaves|plant)s?\b", r"\b(leaf|leaves|plant)s?\b.{0,25}\b(brown|black|pale)\b"], "source": "icar_ipm"},
    "fruit_cracking": {"patterns": [r"\b(crack|cracking|split|splitting)\b.{0,25}\b(fruit|tomato|pomegranate|citrus|mango)s?\b", r"\b(fruit|tomato|pomegranate|citrus|mango)s?\b.{0,25}\b(crack|cracking|split|splitting)\b"], "source": "icar_ipm"},
    "fruit_drop": {"patterns": [r"\b(flower|fruit)s?\b.{0,25}\b(drop|dropping|fall|falling)\b", r"\b(drop|dropping|fall|falling)\b.{0,25}\b(flower|fruit)s?\b"], "source": "icar_ipm"},
    "flowering": {"patterns": [r"\b(no|poor|low|not)\b.{0,20}\b(flower|flowering|fruit set)\b", r"\b(flowering|blossom|fruit set)\b.{0,20}\b(problem|poor|low|not)\b"], "source": "icar_ipm"},
    "stunting": {"patterns": [r"\b(stunt|stunted|slow growth|not growing|small plant)\b"], "source": "icar_ipm"},
    "pest_management": {"patterns": [r"\b(pest|insect|aphid|whitefly|caterpillar|borer|mite|weevil|worm|nematode)s?\b", r"\b(pesticide|spray|insecticide|fungicide|organic control)\b", r"\bmanage pests?\b"], "source": "icar_ipm"},
    "disease": {"patterns": [r"\b(disease|infect|fungal|bacterial|virus|viral|rot|mosaic|blight|mildew)s?\b", r"\bdiagnos(e|is)\b"], "source": "icar_ipm"},
    "overwatering": {"patterns": [r"\b(overwater|overwatering|too much water|waterlogged|water logging|standing water)\b"], "source": "icar_crop_advisory"},
    "underwatering": {"patterns": [r"\b(underwater|underwatering|too little water|not enough water|drought stress|dry soil)\b"], "source": "icar_crop_advisory"},
    "irrigation": {"patterns": [r"\b(water|watering|irrigat\w*|drip|sprinkler|furrow|rainwater|moisture)\b"], "source": "icar_crop_advisory"},
    "soil_ph": {"patterns": [r"\b(ph|acidic soil|alkaline soil|lime|liming|sulfur|sulphur)\b"], "source": "icar_kvk"},
    "soil_test": {"patterns": [r"\b(soil test|soil testing|soil health|soil type|soil texture|soil structure|compaction|salinity|erosion|waterlogging)\b"], "source": "icar_kvk"},
    "nutrient_deficiency": {"patterns": [r"\b(deficienc|deficient|nutrient|nitrogen|phosphorus|potassium|iron|zinc|magnesium|calcium|boron|micronutrient)s?\b"], "source": "icar_kvk"},
    "fertilizer": {"patterns": [r"\b(fertilizer|fertiliser|fertilize|fertilise|manure|npk|dose|application rate)\b"], "source": "icar_kvk"},
    "compost": {"patterns": [r"\b(compost|vermicompost|organic matter|farmyard manure|green manure)\b"], "source": "icar_kvk"},
    "seedling": {"patterns": [r"\b(seed|seeds|germinat|nursery|transplant|sowing|sow|planting time|planting method)\b"], "source": "icar_crop_advisory"},
    "weeds": {"patterns": [r"\b(weed|weeds|weeding|weed control)\b"], "source": "icar_crop_advisory"},
    "rotation": {"patterns": [r"\b(rotation|crop rotation|intercrop|intercropping|cover crop|cover crops|diversif)\b"], "source": "fao_ffs"},
    "sustainable": {"patterns": [r"\b(sustainable|sustainability|organic farming|conservation agriculture|climate resilient|regenerative|natural farming|integrated nutrient)\b"], "source": "fao_ffs"},
    "seasons": {"patterns": [r"\b(kharif|rabi|zaid|crop calendar|cropping season|monsoon season)\b"], "source": "icar_crop_advisory"},
    "schemes": {"patterns": [r"\b(government scheme|subsidy|scheme eligibility|yojana|government benefit|application deadline)\b"], "source": "icar_kvk"},
    "definition": {"patterns": [r"\b(what is|define|meaning of|explain)\b.{0,35}\b(agriculture|farming|ipm|soil|compost|mulch|intercrop|crop rotation|transpiration|photosynthesis|fertigation|drip irrigation|organic farming)\b"], "source": "fao_ffs"},
    "cultivation": {"patterns": [r"\b(grow|growing|cultivat|care for|care of|care does|plant care|crop care|how to plant|how do i grow)\b"], "source": "crop"},
}


RULE_RESPONSES = {
    "live_market": "I cannot verify live market prices in this local Assistant. Check the Market & Profits feature for its current source and freshness; do not treat sample prices as live quotes.",
    "live_weather": "I cannot verify current weather or a forecast from this local Assistant. Check the Weather feature for its source, location, and update time before changing irrigation or crop protection.",
    "economics": "Use recorded quantities, verified prices, and actual costs. Basic checks are gross revenue = saleable quantity × price; net return = revenue − all costs; break-even price = total costs ÷ saleable quantity. These are formulas, not a price or profit forecast. If values are missing, the estimate is incomplete.",
    "yellowing": "Yellow leaves have several possible causes, including natural aging, root stress from too little or too much water, nutrient issues, pests, or disease. Check whether older or newer leaves are affected, whether the pattern is uniform or patchy, soil moisture and drainage, and the undersides of leaves. Similar symptoms can have different causes; this is not a diagnosis. What crop and growth stage are affected, and where did the yellowing start?",
    "wilting": "Wilting can result from dry soil, waterlogged roots, heat, root injury, or disease. Check soil moisture below the surface, drainage, time of day, and whether one plant or a whole area is affected before watering or treating. Do not add water automatically if the soil is wet. What crop is affected, and is the soil dry or wet around the roots?",
    "leaf_curl": "Leaf curl can be caused by heat or water stress, insects such as sap feeders, herbicide drift, viruses, or other disorders. Inspect new growth and leaf undersides, compare affected and healthy plants, and note whether symptoms are spreading. Avoid pesticide use until the cause is better identified. What crop, leaf age, and visible insects or spots do you see?",
    "leaf_spots": "Leaf spots or blight-like symptoms may be caused by fungi, bacteria, insects, spray injury, or weather damage. Note spot shape, color, whether lesions have halos, which leaves are affected, and recent rain or spraying. Remove severely affected fallen material where practical, avoid handling wet plants, and seek a local diagnosis before treatment.",
    "leaf_discoloration": "Brown, black, or pale plant tissue can result from heat or cold injury, water stress, physical or spray damage, nutrient issues, pests, or disease. Check which plant parts are affected, how quickly symptoms appeared, soil moisture, recent weather, and any recent sprays. These signs alone do not confirm a cause; share the crop and symptom pattern or seek a local diagnosis.",
    "fruit_cracking": "Fruit cracking can follow rapid changes in soil moisture and water availability, but cultivar, maturity, temperature, and disease can also matter. Keep irrigation as even as practical, maintain soil cover where suitable, and harvest at the recommended maturity stage. Cracking alone does not identify one cause. Which crop and fruit stage are involved, and did rainfall or watering change recently?",
    "fruit_drop": "Flower or young-fruit drop can follow heat, water stress, poor pollination, nutrient imbalance, pests, or normal crop thinning. Check crop stage, recent weather, moisture, and pest signs; avoid adding fertilizer or spray without evidence. Which crop and stage are affected, and how widespread is the drop?",
    "flowering": "Poor flowering or fruit set can relate to variety, crop age, temperature, light, water stress, nutrition, pollination, or pest damage. Check the crop stage and recent conditions; do not apply a bloom stimulant or high-dose fertilizer without local advice. What crop, variety, and growth stage are involved?",
    "stunting": "Stunted growth can result from poor establishment, compacted or waterlogged soil, weeds, root damage, unsuitable temperature, pests, disease, or nutrient limits. Compare plant roots and soil conditions with healthy plants nearby, and check seed, planting date, and irrigation records before treating.",
    "pest_management": "Use integrated pest management: identify the organism, scout the crop regularly, estimate the affected area, preserve beneficial organisms, and start with suitable cultural, physical, or biological measures. If a pesticide is considered, use only a product registered for that crop and pest, follow its current label and protective-equipment requirements, and get local extension advice. I cannot safely prescribe a product or dose from this question alone.",
    "disease": "I cannot confirm a plant disease from a text description alone. Several diseases and non-disease stresses look alike. Record the crop and variety, affected plant parts, symptom pattern, spread, recent weather and field practices; use a clear sample or photos with a local KVK or qualified plant-health expert. Avoid mixing or applying chemicals without a confirmed, locally appropriate recommendation.",
    "overwatering": "Too much water can reduce oxygen around roots and may cause yellowing, wilting despite wet soil, root damage, or increased disease risk. Check moisture below the surface and whether water drains away; waterlogged soil is a warning sign. Pause irrigation until the root zone needs it, while avoiding drought stress. Soil type, rainfall, crop stage, and irrigation method determine timing.",
    "underwatering": "Underwatering may cause dry soil, loss of leaf firmness, curling, flower or fruit drop, or slower growth, but these symptoms are not specific. Check moisture in the active root zone and recent heat or wind. Water the root zone evenly when needed; avoid an exact schedule without soil, crop stage, and weather information.",
    "irrigation": "Choose irrigation based on crop stage, soil texture, drainage, rainfall, and the water source. Drip can target the root zone; sprinklers wet foliage and can increase some disease risks; furrow or surface methods need attention to uniformity and runoff. Check root-zone moisture rather than following a fixed calendar. What crop, soil type, and irrigation method do you use?",
    "soil_ph": "Soil pH affects nutrient availability, but the useful range depends on the crop and soil. Get a representative soil test before applying lime or sulfur; the amount needed depends on soil texture and buffering capacity. Do not choose a correction rate from pH alone. An ICAR KVK can help interpret a local soil test.",
    "soil_test": "A soil test is the best starting point for pH and nutrient decisions. Sample representative parts of the field separately when soil or management differs, avoid unusual spots such as compost heaps, and follow the laboratory's depth and sampling instructions. Use the report and crop plan together; a visual symptom alone is not a soil test.",
    "nutrient_deficiency": "Nutrient symptoms overlap with water stress, root problems, pests, and disease. Leaf age and symptom pattern can offer clues, but confirm with a soil or plant test when possible before applying nutrients. Excess fertilizer can harm crops and water quality. Share the crop, leaf age, symptom pattern, and any test results for a more useful discussion.",
    "fertilizer": "Fertilizer type and amount depend on crop, variety, soil-test results, target yield, and locally approved recommendations. Use a soil test and split nutrients as advised for the crop and stage; avoid copying a rate from another region or applying fertilizer to a stressed crop without diagnosis. I cannot provide a safe precise dose from the information given.",
    "compost": "Mature, well-handled compost can add organic matter and support soil structure, but its nutrient content varies. Use clean feedstock, allow compost to mature, and account for its nutrients in the crop plan. Compost does not automatically replace a soil test or a crop-specific nutrient recommendation.",
    "seedling": "Use healthy, correctly identified seed or planting material suited to the local season. Prepare a clean nursery or seedbed, avoid waterlogging, and harden seedlings before transplanting where appropriate. Sowing depth, spacing, seed treatment, and transplant age are crop- and variety-specific; use the current local package of practices.",
    "weeds": "Control weeds early while the crop is establishing, using suitable mulching, hand or mechanical weeding, crop rotation, and competitive crop stands where appropriate. Identify the weed and crop stage before considering herbicides; follow local labels and advice. Prevent weeds from setting seed when practical.",
    "rotation": "Crop rotation changes crop families over time and can interrupt some pest and disease cycles, diversify rooting patterns, and spread labor and market risk. Choose crops that fit local water, soil, season, and market conditions; rotation benefits are pest- and site-specific, not guaranteed.",
    "sustainable": "Sustainable farming combines practices suited to local soil, water, crop, and livelihood needs. Options include keeping soil covered, rotating crops, recycling safe organic material, improving water efficiency, and monitoring pests before intervention. Each option has trade-offs; compare labor, input, water, and market constraints on your farm.",
    "seasons": "In India, Kharif crops are generally associated with the monsoon, Rabi with the cooler post-monsoon season, and Zaid with a short summer season between them. Exact sowing and harvest windows vary by state, elevation, irrigation, and crop variety. Use a current ICAR or state agricultural university advisory for your district.",
    "schemes": "Government scheme eligibility, benefits, application windows, and documents can change and vary by state. I cannot verify current scheme rules offline. Check the official state or central agriculture department portal, or ask your district agriculture office or KVK; do not rely on an undated summary.",
    "storage": "Post-harvest handling depends on crop and maturity. Sort damaged produce, minimize bruising, keep containers and storage areas clean, and use temperature and humidity conditions suited to that crop. I cannot verify a shelf life or facility availability without current crop-specific and local data.",
    "definition": "Integrated Pest Management (IPM) combines prevention, observation, and suitable control methods, giving priority to approaches that manage pests while limiting unnecessary risk to people and the environment. The choice depends on the crop, organism, and local conditions.",
    "cultivation": "Start with a locally adapted variety and planting window. Prepare a well-drained seedbed, establish a uniform stand, manage weeds early, and adjust water and nutrients to crop stage and soil-test guidance. Exact spacing, fertilizer rates, and dates are regional and variety-specific.",
    "general": "I can help with general crop care, soil, water, common symptoms, pests, harvest, storage, sustainability, farm economics, Indian seasons, and AgriSense AI. I do not have a reliable local rule for this exact question yet. Share the crop, location, growth stage, and what you observed, or contact your district KVK for a field-specific advisory.",
}


PROJECT_ANSWERS = {
    "project": "AgriSense AI is a farming-support website with crop tools, weather and market features, storage information, news, and an Assistant. This Assistant now uses local text normalization, crop aliases, question-intent rules, and a curated static knowledge base; it does not call Gemini, Groq, or a generative model. It can use authenticated account-scoped farm-tool records when present. Shared seeded crop rows are treated as examples, not as the signed-in farmer's records. Unsupported questions receive an explicit limitation and a follow-up or local-extension suggestion. Other website features retain their separate integrations and may use APIs; the local Assistant does not claim current weather, prices, diagnosis, or account data it cannot verify.",
}


def normalize_question(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("’", "'").replace("can't", "cannot").replace("don't", "do not")
    text = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "tomatos": "tomato", "potatos": "potato", "mangos": "mango",
        "chillies": "chilli", "chilies": "chilli", "ladies finger": "lady finger",
        "bhendi": "okra", "baingan": "brinjal", "kheera": "cucumber",
        "gobhi": "cauliflower", "gehu": "wheat", "makka": "maize",
    }
    for old, new in replacements.items():
        text = re.sub(r"\b" + re.escape(old) + r"\b", new, text)
    return text


def recognize_crop(question: str, crop_hint: str = "") -> tuple[str | None, bool]:
    text = normalize_question(question)
    aliases: list[tuple[str, str]] = []
    for canonical, profile in CROP_PROFILES.items():
        aliases.extend((alias, canonical) for alias in profile["aliases"].split())
        # Preserve multiword aliases as a single match.
        aliases.extend((alias, canonical) for alias in profile["aliases"].split("  ") if alias.strip())
    # The alias field is space-delimited; recognize useful multiword forms
    # separately so a constituent such as "bean" does not override the crop.
    multiword = [
        (phrase, canonical)
        for canonical, profile in CROP_PROFILES.items()
        for phrase in ("bitter gourd", "bottle gourd", "ridge gourd", "finger millet", "pearl millet", "pigeon pea", "black gram", "french beans", "french bean", "green beans", "green bean", "lady finger", "ladyfinger", "sugar cane")
        if phrase in profile["aliases"]
    ]
    for alias, canonical in sorted(multiword, key=lambda item: len(item[0]), reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", text):
            return canonical, True
    for alias, canonical in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", text):
            return canonical, True
    known_aliases = [(alias, canonical) for alias, canonical in aliases if len(alias) >= 5]
    for word in text.split():
        match = difflib.get_close_matches(word, [alias for alias, _ in known_aliases], n=1, cutoff=0.88)
        if match:
            canonical = next(crop for alias, crop in known_aliases if alias == match[0])
            return canonical, True
    hint = normalize_question(crop_hint)
    for canonical, profile in CROP_PROFILES.items():
        if re.search(r"\b" + re.escape(canonical) + r"\b", hint):
            return canonical, False
        for alias in profile["aliases"].split():
            if len(alias) > 3 and re.search(r"\b" + re.escape(alias) + r"\b", hint):
                return canonical, False
    return None, False


def detect_intent(question: str) -> str:
    for intent, rule in INTENTS.items():
        if any(re.search(pattern, question) for pattern in rule["patterns"]):
            return intent
    return "general"


def _safe_record_line(record: dict[str, Any]) -> str:
    kind = str(record.get("kind", "record")).replace("-", " ")
    fields = record.get("data") if isinstance(record.get("data"), dict) else record
    allowed = ("crop", "stage", "planting_date", "harvest_date", "expected_harvest_date", "title", "date", "priority", "status", "quantity", "unit", "sold", "stored", "spoiled", "scenario", "net", "gross_revenue", "total_expenses")
    details = [f"{key.replace('_', ' ')}: {str(fields[key])[:80]}" for key in allowed if fields.get(key) not in (None, "")]
    return f"- {kind.title()}" + (" — " + "; ".join(details) if details else "")


def _farm_record_answer(question: str, records: list[dict[str, Any]], shared_crops: list[dict[str, Any]]) -> str:
    crop, _ = recognize_crop(question)
    selected = []
    for record in records:
        data = record.get("data") if isinstance(record.get("data"), dict) else record
        crop_value = str(data.get("crop", ""))
        if crop is None or recognize_crop(crop_value)[0] == crop:
            selected.append(record)
    if selected:
        lines = [_safe_record_line(record) for record in selected[:8]]
        return "These are account-scoped records marked USER ENTERED in AgriSense:\n" + "\n".join(lines) + ("\nShowing the most recent 8 matching records." if len(selected) > 8 else "")
    shared_names = [str(row.get("name")) for row in shared_crops if row.get("name")]
    if shared_names:
        return ("I found no matching account-specific USER ENTERED farm records. The shared crop table contains example records for "
                + ", ".join(shared_names[:8])
                + "; those rows are shared seed/sample data and are not confirmed as your farm. Sign in and save a crop or farm-tool record to get account-specific answers.")
    return "I found no matching account-specific USER ENTERED farm records. I will not infer your farm details from general crop guidance. Sign in and save a crop, task, harvest, or planning record to get an account-specific answer."


def answer_question(
    message: str,
    crop_hint: str = "",
    farm_records: list[dict[str, Any]] | None = None,
    shared_crops: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    question = normalize_question(message)
    crop, explicit_crop = recognize_crop(question, crop_hint)
    intent = detect_intent(question)
    if intent == "project":
        answer = PROJECT_ANSWERS["project"]
    elif intent == "farm_records":
        answer = _farm_record_answer(question, farm_records or [], shared_crops or [])
    else:
        answer = RULE_RESPONSES.get(intent, RULE_RESPONSES["general"])

    profile = CROP_PROFILES.get(crop) if crop else None
    if profile and intent in {"cultivation", "irrigation", "overwatering", "underwatering", "seedling", "harvest", "storage"}:
        crop_detail = profile["harvest"] if intent == "harvest" else profile["care"]
        answer += f"\n\n{crop.title()} note: {crop_detail}"
        if not explicit_crop and crop_hint:
            answer += " This uses the Assistant's supplied crop context; mention another crop to focus the answer."
    elif profile and intent == "general" and explicit_crop:
        answer = f"For {crop}, a useful starting point is: {profile['care']} Ask about watering, symptoms, soil, pests, cultivation, or harvest for more focused guidance."

    source_key = INTENTS.get(intent, {}).get("source")
    if intent == "project":
        source_lines = ["Architecture summary is based on this project's implementation."]
    elif source_key == "crop":
        source_lines = [f"For region-specific crop schedules and recommendations, check the [ICAR agro-advisory]({SOURCES['icar_crop_advisory']['url']}) or contact a [district KVK]({SOURCES['icar_kvk']['url']})."]
    elif source_key in SOURCES:
        source = SOURCES[source_key]
        source_lines = [f"Reference: [{source['name']}]({source['url']}). Use current local advice for region- and variety-specific decisions."]
        if source_key in {"icar_ipm", "icar_kvk"}:
            source_lines.append(f"Additional reference: [{SOURCES['fao_ffs']['name']}]({SOURCES['fao_ffs']['url']}).")
    else:
        source_lines = []
    if source_lines:
        answer += "\n\n" + "\n".join(source_lines)

    return {
        "answer": answer,
        "intent": intent,
        "crop": crop,
        "used_farm_records": bool(intent == "farm_records" and farm_records),
        "data_source": "LOCAL RULE-BASED KNOWLEDGE" + ("; USER ENTERED FARM RECORDS" if intent == "farm_records" and farm_records else "; SHARED SAMPLE DATA (not account-specific)" if intent == "farm_records" and shared_crops else ""),
    }


def knowledge_stats() -> dict[str, int]:
    return {
        "crop_profiles": len(CROP_PROFILES),
        "intent_entries": len(INTENTS),
        "question_patterns": sum(len(rule["patterns"]) for rule in INTENTS.values()),
        "project_entries": len(PROJECT_ANSWERS),
    }
