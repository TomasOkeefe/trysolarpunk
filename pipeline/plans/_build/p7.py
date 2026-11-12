from dsl import S, save
G = "Flat grey light."
M = "Bright morning sun."
N = "Bright midday sun."
A = "Golden afternoon light."
E = "Golden evening light."
SING = "Close-up: {moss} sings to the camera, his mouth opening wide under his bushy mustache, "
GRAN = "a grandma in a purple cardigan and pearl glasses"
BAKER = "a baker in a white apron and a tall white hat"
KIDS = "two small children in red dungarees with pigtails"
save({
 "slug": "grey-wall", "date": "2026-11-18", "product": "hibernator", "style": "claymation",
 "hook_text": "The grey wall was bugging me",
 "song": {"title": "Paint It",
  "style": "English, bright funk with slap bass, wah guitar, tight horn stabs and cowbell, warm friendly male lead vocal, joyful and groovy, 122 BPM",
  "lyrics": "[Verse]\nGrey old wall across the way\nStared at it most every day\nScrolling colours on a screen\nWhile my street was never seen\n\n[Chorus]\nPaint it, paint it, red and blue\nDrips of yellow on my shoe\nPaint it, paint it, big and bright\nPhone's asleep till late tonight\n\n[Verse]\nGrandma drew a purple cat\nBaker made a giant hat\nKids left handprints, green and gold\nA sunflower, ten feet tall and bold\n\n[Chorus]\nPaint it, paint it, red and blue\nWhole street's got a job to do\nPaint it, paint it, step on back\nNo more grey, and that's a fact"},
 "shots": [
  S(0, f"A long blank grey wall faces a row of crooked clay houses across a narrow street, dull under a grey sky. The camera cranes down to it. {G}"),
  S(None, f"{{moss}} stands at his window with a mug, staring out at a blank grey wall across the street. The camera dolly zooms on him from outside. {G}",
    frame=f"He stands at a window holding a mug, seen from outside through the glass, looking out with a bored face. Medium shot. {G}"),
  S(1, f"{{moss}} sits on a doorstep with his chin in his hands, staring at a blank grey wall across a narrow street. The camera orbits around him. {G}"),
  S(None, f"A grey pigeon on top of a blank grey wall yawns and tucks its head under its wing. Close-up, the camera pushes in. {G}"),
  S(2, "A softly glowing phone held in two clay hands swirls with rainbow colours. Extreme close-up, the camera spins around it. Dim grey light."),
  S(None, "{moss} sits on a green sofa, his round glasses reflecting swirling rainbow colours from a softly glowing phone. Close-up, the camera pushes in. Dim grey light, warm lamp."),
  S(3, SING + "wistful, a blank grey wall filling the window behind him. The camera pushes in. Flat grey light, warm lamp.", sing=True),
  S(None, "{moss} looks from his phone to the grey wall outside his window and back, and a grin spreads under his mustache. The camera whip-pans between them. Warm lamp light."),
  S(4, f"{{moss}} kicks open a shed door and marches out carrying a red tin of paint and a blue tin of paint, a brush between his teeth. The camera crash zooms in. {M}",
    frame=f"He stands in the doorway of a garden shed holding a red tin of paint in one hand and a blue tin of paint in the other, a paintbrush held in his teeth. Full body. {M}"),
  S(None, f"A fat paintbrush dips into a tin of bright red paint and comes up dripping. Extreme close-up, the camera tilts up with it. {M}"),
  S(5, f"{{moss}} slaps a big stripe of yellow paint onto a grey wall and a blob drips onto his green boot. The camera tilts down from the brush to his boot. {M}", view="side",
    frame=f"He stands side-on at a blank grey wall holding a fat paintbrush loaded with yellow paint up against it, a tin of yellow paint at his feet. Full body. {M}"),
  S(None, f"A blob of yellow paint lands on the toe of a green rubber boot. Extreme close-up, the camera crash zooms in. {M}"),
  S(6, f"{{moss_back}} paints a huge red swirl on a grey wall with a roller on a long pole, stretching up on tiptoe. The camera cranes up along the wall. {M}"),
  S(None, f"{{moss}} turns away from a wall with red and blue paint splattered on his raincoat, beaming. The camera pushes in fast. {M}"),
  S(7, "A black smartphone stands upright, face to the door, in a quilted moss-green brick stuck to a cream fridge door, a round sun-yellow badge with a closed eye on its front, a small shopping list held by a yellow magnet beside it. Soft leaf shadows sway slowly across the fridge door. Warm morning light. The camera pushes in slowly.", product=True),
  S(None, f"A grey pigeon on top of a wall looks down at a wet red swirl of paint and tilts its head. Close-up, the camera pushes in. {M}"),
  S(8, f"{GRAN[0].upper() + GRAN[1:]} paints a big purple cat on a grey wall with a tiny brush, tongue out. The camera pushes in. {N}"),
  S(None, f"A big purple cat with a curly tail painted on a wall, still wet and shining. The camera orbits past it. {N}", props=True),
  S(9, f"{BAKER[0].upper() + BAKER[1:]} paints a giant white chef's hat on a grey wall with a broom dipped in paint. The camera cranes up the wall. {N}"),
  S(None, f"{{moss}} and {BAKER} clink their paintbrushes together like a toast. The camera crash zooms in. {N}"),
  S(10, f"{{moss}} holds out a tray of green and gold paint while {KIDS} press handprints onto a wall, giggling. The camera tracks along the wall. {N}"),
  S(None, f"A small clay hand presses a new gold handprint into a row of green and gold handprints on a wall. Close-up, the camera pushes in. {N}"),
  S(11, f"{{moss_back}} stands on a wooden ladder painting the yellow petals of a giant sunflower high on a wall. The camera cranes up the ladder to him. {A}"),
  S(None, f"A giant painted sunflower with a smiling face towers on a wall above a street. The camera tilts up its stem to the flower. {A}", props=True),
  S(12, SING + f"joyful, speckled with red, blue and yellow paint, a colourful painted wall behind him. The camera orbits around him. {A}", sing=True),
  S(None, f"Clay hands holding paintbrushes of every colour swish across a wall together. Close-up, the camera whip-pans along the wall. {A}"),
  S(13, f"{{moss_back}} paints at one long wall beside {GRAN} and {BAKER}, ladders and tins of paint all along the street. The camera tracks fast along the wall. {A}"),
  S(None, f"A grey pigeon with blue paint on its feet walks along the top of a wall leaving little blue footprints. Close-up, the camera tracks with it. {A}"),
  S(14, f"{{moss}} steps backward across the street, paintbrush in hand, looking up in awe. The camera tracks backward with him. {E}"),
  S(None, f"A long wall covered in a bright mural: a giant sunflower, a purple cat, a white chef's hat, a red swirl and rows of handprints. The camera cranes up and back to reveal it all. {E}", props=True),
  S(15, f"{{moss}}, {GRAN} and {BAKER} sit side by side on a doorstep with mugs, speckled with paint, smiling at something across the street. The camera pulls back slowly. {E}",
    frame=f"He sits in the middle of a doorstep in his mustard-yellow raincoat holding a mug, speckled with paint, smiling. On one side of him sits {GRAN}, on the other side sits {BAKER}, each holding a mug. Three people in a row. Medium shot. {E}"),
  S(None, "{moss_back} sits on a doorstep at dusk with a mug, looking at a bright mural of a giant sunflower glowing under a streetlamp, and takes a deep breath. The camera cranes slowly up. Warm streetlamp glow, deep blue dusk."),
 ],
 "endcard": {"line1": "Paint the wall.", "line2": "link in bio"},
 "caption": "moss stared at the grey wall for years. then his phone went in the Hibernator and the paint came out. the pigeon helped",
 "hashtags": ["#mural", "#streetart", "#claymation", "#solarpunk", "#community"],
})
