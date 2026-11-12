from dsl import S, save
M = "Bright morning sun."
D = "Dusty golden sunbeams."
N = "Bright midday sun."
E = "Golden evening light."
SING = "Close-up: {moss} sings to the camera, his mouth opening wide under his bushy mustache, "
GRAN = "a grandma in a purple cardigan and pearl glasses"
POST = "a postman in a blue uniform with a big ginger mustache"
save({
 "slug": "whistle-back", "date": "2026-11-13", "product": "eyelid", "style": "claymation",
 "hook_text": "My phone napped. I learned to whistle",
 "song": {"title": "Whistle Back",
  "style": "English, breezy skiffle folk with washboard, upright bass, strummed acoustic guitar and a whistled hook, warm friendly male lead vocal, sunny and light, 118 BPM",
  "lyrics": "[Verse]\nEvery ping would turn my head\nBuzzing by my morning bread\nTucked my phone in for a nap\nEyelid shut, and that was that\n\n[Chorus]\nWhistle, whistle, try again\nSounds like wind in a watering can\nWhistle, whistle, there it goes\nA blackbird answered from the rose\n\n[Verse]\nPractised in the garden shed\nRobin landed on my head\nSparrows on the washing line\nEvery beak in perfect time\n\n[Chorus]\nWhistle, whistle, loud and clear\nWhole street stopped to lend an ear\nWhistle, whistle, off we go\nMe and the birds put on a show"},
 "shots": [
  S(0, "{moss} sits at a breakfast table, toast halfway to his mouth, and his head snaps toward a phone on the table that buzzes and glows softly. The camera whip-pans from his face to the phone. Bright morning kitchen light.",
    frame="He sits at a breakfast table holding a slice of toast halfway to his mouth, looking sideways at a phone lying on the table. Medium shot. Bright morning kitchen light."),
  S(None, "A phone buzzes its way across a wooden table, rattling a teaspoon in a cup. Extreme close-up, the camera tracks with it. Bright morning light."),
  S(1, SING + "grumpy, a slice of toast in his hand, in a sunny kitchen. The camera pushes in. Bright morning light.", sing=True),
  S(None, "A slice of toast with jam slips from a clay hand and lands jam side down on a plate. Close-up, the camera tilts down fast. Bright morning light."),
  S(2, "{moss} slides a phone into a slim terracotta-orange sleeve whose top edge looks like a closed eyelid with black lashes, then pats it gently. The camera pushes in on his hands. Warm morning light.",
    frame="He stands at a kitchen table holding a phone in one hand and a slim terracotta-orange sleeve in the other, about to slide the phone in. Medium shot. Warm morning light."),
  S(3, "A slim terracotta-orange sleeve stands upright on a soft pale green backdrop, a phone tucked inside so only its top edge peeks out, the sleeve's top edge cut like a closed eyelid with black lashes. Soft leaf shadows drift across the backdrop. Warm daylight. The camera slowly pushes in as the light turns warmer.", product=True),
  S(None, "{moss} leans back in his chair in the sudden quiet, looks around the kitchen and puckers his lips. The camera dolly zooms on him. Warm morning light."),
  S(4, SING + f"cheeks puffed, in a garden full of flowers. The camera pushes in fast. {M}", sing=True),
  S(None, f"{{moss}} blows hard with puffed red cheeks and only a tiny puff of air comes out, his mustache flapping. Close-up, the camera crash zooms in. {M}"),
  S(5, f"A dented green watering can wobbles on a garden path as wind whistles across its spout. Close-up, the camera orbits it. {M}"),
  S(None, f"{{moss}} stands among the flowers trying to whistle, face scrunched, one finger raised like a conductor. The camera orbits fast around him. {M}"),
  S(6, f"{{moss}} whistles and his eyes go wide with surprise as a clear note comes out, his beanie's pom-pom bouncing. The camera crash zooms in. {M}"),
  S(None, f"The leaves of a rose bush tremble as a sweet note rings through the garden. The camera whip-pans across the garden to the bush. {M}"),
  S(7, f"A glossy blackbird with a bright orange beak sits on a blooming rose bush, tilts its head and opens its beak to sing back. Close-up, the camera pushes in. {M}"),
  S(None, f"{{moss}} gasps and points at a blackbird on a rose bush, bouncing on his toes. The camera whip-pans from him to the bird. {M}", view="threeq"),
  S(8, f"{{moss}} stands in a cosy wooden garden shed full of flowerpots, practising his whistle with his eyes closed. The camera pushes in through the shed door. {D}"),
  S(None, f"Flowerpots on a shelf in a garden shed rattle and hop in time to a tune. Close-up, the camera tracks along the shelf. {D}"),
  S(9, f"A small round robin with a red breast flutters down and lands right on top of {{moss}}'s green beanie, and he freezes, eyes rolling up to look. The camera crash zooms in. {D}",
    frame=f"He stands in the doorway of a garden shed looking up with wide eyes, a small round robin with a red breast perched on top of his green beanie. Medium shot. {D}"),
  S(None, f"{{moss}} slowly breaks into a grin with a robin perched on his beanie. Close-up, the camera pushes in. {D}",
    frame=f"A close-up of him smiling a little, a small round robin with a red breast perched on top of his green beanie, in a garden shed. {D}", view="face"),
  S(10, f"Five plump brown sparrows land one by one on a washing line hung with striped socks. The camera tracks along the line. {N}"),
  S(None, f"{{moss}} stands in a garden waving a wooden spoon like a conductor's baton at five plump sparrows on a washing line. The camera orbits around him. {N}"),
  S(11, f"Five plump brown sparrows on a washing line open their beaks all together, bobbing in rhythm. Close-up, the camera whip-pans along them. {N}"),
  S(None, f"{{moss}} whistles with his eyes closed, swaying, a robin on his beanie swaying with him. The camera orbits slowly. {N}"),
  S(12, SING + f"joyful, a robin perched on his beanie, in a sunny garden. The camera pushes in fast. {N}", sing=True),
  S(None, f"{{moss}} marches down a garden path whistling, a blackbird, a robin and sparrows flying in a line behind him. The camera tracks backward in front of him. {N}"),
  S(13, f"{{moss}} walks down a street of crooked clay houses whistling, and {POST} and {GRAN} stop and turn their heads to listen as he passes. The camera cranes down to them. Bright afternoon sun."),
  S(None, f"{GRAN[0].upper() + GRAN[1:]} cups a hand to her ear and smiles. Close-up, the camera pushes in. Bright afternoon sun."),
  S(14, "{moss} strides along a street whistling, small birds perched along both of his outstretched arms. The camera tracks beside him. Golden afternoon light.", view="side"),
  S(None, f"{POST[0].upper() + POST[1:]} whistles along and tosses his cap in the air. The camera crash zooms in. Golden afternoon light."),
  S(15, f"{{moss}} stands on an upturned crate in a little town square whistling, a blackbird on one hand and sparrows on his shoulders, while {GRAN} claps. The camera cranes up and around. {E}"),
  S(None, f"A row of little birds on a rooftop gutter sing into a golden sunset. The camera cranes up past them into the sky. {E}"),
  S(None, f"{{moss}} sits on a garden bench at sunset with a robin asleep on his beanie and breathes out slowly with a small smile. The camera pulls back slowly. {E}"),
 ],
 "endcard": {"line1": "Whistle back.", "line2": "link in bio"},
 "caption": "moss tucked his phone into the Eyelid and learned to whistle. the birds had notes. now they tour together",
 "hashtags": ["#whistle", "#birdsong", "#claymation", "#solarpunk", "#phonefree"],
})
