import requests
from flask import Flask, render_template, request, jsonify, session
import os
from dotenv import load_dotenv
import openai
import json
import random

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

openai.api_key = os.getenv('OPENAI_API_KEY')

LANGUAGES = {
    'python': 'Python',
    'java': 'Java',
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'csharp': 'C#',
    'ruby': 'Ruby'
}

FRAMEWORKS = {
    'selenium': 'Selenium',
    'playwright': 'Playwright',
    'cypress': 'Cypress',
    'robot': 'Robot Framework',
    'cucumber': 'Cucumber',
    'pytest': 'Pytest'
}


class QuestionGenerator:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "QA Interview Prep"
        }

    def generate_questions(self, language, framework, category, count=3):
        if not self.api_key:
            raise ValueError("Не вказано API ключ OpenRouter")

        prompts = {
            'qc_theory': f"""
            Створи {count} питань українською з теорії тестування ПЗ.
            Формат: {{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A"}}]}}
            """,
            'automation_theory': f"""
            Створи {count} питань українською з автоматизації тестування.
            Формат: {{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A"}}]}}
            """,
            'language': f"""
            Створи {count} питань українською про {LANGUAGES[language]} для тестування.
            Формат: {{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A"}}]}}
            """,
            'framework': f"""
            Створи {count} питань українською про {FRAMEWORKS[framework]}.
            Формат: {{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A"}}]}}
            """
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": "mistralai/mistral-7b-instruct",  # Безкоштовна модель
                    "messages": [
                        {"role": "system", "content": "Ти експерт QA. Генеруй технічні питання українською."},
                        {"role": "user", "content": prompts[category]}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
            )

            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            questions = self._parse_response(content)
            return questions[:count]

        except Exception as e:
            print(f"Помилка генерації через OpenRouter: {str(e)}")
            raise

    def _parse_response(self, content):
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            json_str = content[start:end]
            data = json.loads(json_str)
            return data.get('questions', [])
        except json.JSONDecodeError:
            print("Не вдалося розпарсити відповідь API")
            raise


question_generator = QuestionGenerator()


@app.route('/')
def index():
    return render_template('index.html',
                           languages=LANGUAGES,
                           frameworks=FRAMEWORKS)


@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.get_json()
    language = data.get('language')
    framework = data.get('framework')

    session['language'] = language
    session['framework'] = framework
    session['current_question'] = 0
    session['score'] = 0

    all_questions = []
    categories = ['qc_theory', 'automation_theory', 'language', 'framework']

    for category in categories:
        questions = question_generator.generate_questions(language, framework, category, count=3)
        if questions:
            for q in questions:
                q['category'] = category
            all_questions.extend(questions)

    if not all_questions:
        return jsonify({'status': 'error', 'message': 'Не вдалося згенерувати питання'}), 500

    random.shuffle(all_questions)
    session['questions'] = all_questions

    return jsonify({'status': 'success', 'total_questions': len(all_questions)})


@app.route('/get_question')
def get_question():
    current = session.get('current_question', 0)
    questions = session.get('questions', [])

    if current >= len(questions):
        return jsonify({'finished': True})

    question = questions[current]
    return jsonify({
        'question': question,
        'current': current + 1,
        'total': len(questions)
    })


@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    answer = data.get('answer')

    current = session.get('current_question', 0)
    questions = session.get('questions', [])
    score = session.get('score', 0)

    if current < len(questions):
        correct_answer = questions[current]['correct']
        if answer == correct_answer:
            score += 1
            session['score'] = score

        session['current_question'] = current + 1

        return jsonify({
            'correct': answer == correct_answer,
            'correct_answer': correct_answer
        })

    return jsonify({'error': 'Питання не знайдено'})


@app.route('/results')
def results():
    score = session.get('score', 0)
    total = len(session.get('questions', []))
    language = session.get('language', '')
    framework = session.get('framework', '')

    percentage = round((score / total * 100) if total > 0 else 0, 1)

    return render_template('result.html',
                           score=score,
                           total=total,
                           percentage=percentage,
                           language=LANGUAGES.get(language, ''),
                           framework=FRAMEWORKS.get(framework, ''))


if __name__ == '__main__':
    app.run(debug=True)
