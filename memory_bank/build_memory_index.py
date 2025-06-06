from llama_index import SimpleDirectoryReader, Document
from llama_index import GPTTreeIndex, GPTSimpleVectorIndex
from llama_index.indices.composability import ComposableGraph
import json, openai
from llama_index import LLMPredictor, GPTSimpleVectorIndex, PromptHelper, ServiceContext
# from langchain import OpenAI, AzureOpenAI
from langchain.llms import AzureOpenAI,OpenAIChat
import os
from typing import Optional, List
from openai import OpenAI
from langchain.llms.base import LLM

# 自定义OpenAI API参数
custom_api_key = os.environ["UIH_DS_API_KEY"]
custom_base_url = os.environ["UIH_DS_BASE_URL"]
custom_model = "DeepSeek-V3-0324"
custom_temperature = 0.6

# 创建OpenAI客户端
client = OpenAI(
    api_key=custom_api_key,
    base_url=custom_base_url,
)

# 定义自定义LLM包装器
class CustomOpenAILLM(LLM):
    model: str = custom_model
    temperature: float = custom_temperature
    client: OpenAI = client

    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            stop=stop,
        )
        return response.choices[0].message.content

    @property
    def _llm_type(self) -> str:
        return "deepseek"
    
llm_predictor = LLMPredictor(llm=CustomOpenAILLM())

# define prompt helper
# set maximum input size
max_input_size = 4096
# set number of output tokens
num_output = 256
# set maximum chunk overlap 
max_chunk_overlap = 20


def generate_memory_docs(data,language):
    # data = json.load(open(memory_path,'r',encoding='utf8'))
    all_user_memories = {}
    for user_name, user_memory in data.items():
        # print(user_memory)
        all_user_memories[user_name] = []
        if 'history' not in user_memory.keys():
            continue
        for date, content in user_memory['history'].items():
            memory_str = f'日期{date}的对话内容为：' if language=='cn' else f'Conversation on {date}：'
            for dialog in content:
                query = dialog['query']
                response = dialog['response']
                memory_str += f'\n{user_name}：{query.strip()}'
                memory_str += f'\nAI：{response.strip()}'
            memory_str += '\n'
            if 'summary' in user_memory.keys():
                if date in user_memory['summary'].keys():
                    summary = f'时间{date}的对话总结为：{user_memory["summary"][date]}' if language=='cn' else f'The summary of the conversation on {date} is: {user_memory["summary"][date]}'
                    memory_str += summary
            # if 'personality' in user_memory.keys():
            #     if date in user_memory['personality'].keys():
            #         memory_str += f'日期{date}的对话分析为：{user_memory["personality"][date]}'
            # print(memory_str)
            all_user_memories[user_name].append(Document(memory_str))
    return all_user_memories
            
# all_user_memories = load_data('../memories/update_memory_0512_eng.json')
index_set = {}
def build_memory_index(all_user_memories,data_args,name=None):
    all_user_memories = generate_memory_docs(all_user_memories,data_args.language)
    #llm_predictor = LLMPredictor(llm=OpenAIChat(model_name="gpt-3.5-turbo"))
    prompt_helper = PromptHelper(max_input_size, num_output, max_chunk_overlap)
    service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor, prompt_helper=prompt_helper)
    for user_name, memories in all_user_memories.items():
        # print(all_user_memories[user_name])
        if name:
            if user_name != name:
                continue
        print(f'build index for user {user_name}')
        cur_index = GPTSimpleVectorIndex.from_documents(memories,service_context=service_context)
        index_set[user_name] = cur_index
        os.makedirs(f'../memories/memory_index/llamaindex',exist_ok=True)
        cur_index.save_to_disk(f'../memories/memory_index/llamaindex/{user_name}_index.json')
 
