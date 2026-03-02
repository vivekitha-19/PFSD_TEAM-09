from django.shortcuts import render

# Multi-language advisory data
advisory_data = {
    "Rice": {
        "Leaf": {
            "Leaf Spot": {
                "en": {
                    "solution": "Apply recommended fungicide spray.",
                    "prevention": "Ensure proper drainage and avoid overwatering.",
                    "scheme": "PM-KISAN Scheme Support Available."
                },
                "te": {
                    "solution": "సిఫార్సు చేసిన ఫంగిసైడ్ స్ప్రే ఉపయోగించండి.",
                    "prevention": "నీటి నిల్వలు లేకుండా చూసుకోండి.",
                    "scheme": "పీఎం-కిసాన్ పథకం అందుబాటులో ఉంది."
                },
                "hi": {
                    "solution": "अनुशंसित फफूंदनाशक का छिड़काव करें।",
                    "prevention": "जल निकासी सही रखें।",
                    "scheme": "पीएम-किसान योजना उपलब्ध।"
                }
            }
        }
    }
}

def home(request):
    result = None
    selected_lang = "en"

    if request.method == "POST":
        crop = request.POST.get("crop")
        part = request.POST.get("part")
        disease = request.POST.get("disease")
        selected_lang = request.POST.get("language")

        try:
            result = advisory_data[crop][part][disease][selected_lang]
        except:
            result = None

    return render(request, "index.html", {
        "result": result,
        "selected_lang": selected_lang
    })
