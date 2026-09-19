import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def clean_text(text):
    """
    Clean text before calculating similarity.
    """

    if text is None:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-zA-Z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def calculate_similarity(lost_item, found_item):

    lost_text = clean_text(
        f"{lost_item['item_name']} "
        f"{lost_item['category']} "
        f"{lost_item['description']} "
        f"{lost_item['location']}"
    )

    found_text = clean_text(
        f"{found_item['item_name']} "
        f"{found_item['category']} "
        f"{found_item['description']} "
        f"{found_item['location']}"
    )

    if not lost_text or not found_text:
        return 0.0

    vectorizer = TfidfVectorizer()

    vectors = vectorizer.fit_transform(
        [lost_text, found_text]
    )

    similarity = cosine_similarity(
        vectors[0:1],
        vectors[1:2]
    )[0][0]

    return round(
        float(similarity) * 100,
        2
    )


def get_match_label(score):

    if score >= 80:
        return "High Match"

    elif score >= 60:
        return "Possible Match"

    elif score >= 40:
        return "Low Match"

    else:
        return "Unlikely Match"