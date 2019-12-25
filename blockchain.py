import hashlib
import json
import os
from time import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request, send_from_directory
# from tracecms import trace_cms


class Blockchain:
    def __init__(self):
        self.current_reports = []
        self.chain = []
        self.length = 0
        self.nodes = set()

        self.chain_file = 'data.json'
        self.temp_file = 'temp.json'
        self.node_file = 'nodes.json'

        try:
            with open(filepath + self.chain_file, 'r') as f:
                data = json.load(f)
                self.chain = data['chain']
                self.length = data['length']
        except:
            # 创建创世块
            self.new_block(previous_hash='1', proof=100, miner=node_identifier)

        try:
            with open(filepath + self.temp_file, 'r') as f:
                data = json.load(f)
                self.current_reports = data['temp']
        except:
            pass

        try:
            with open(filepath + self.node_file, 'r') as f:
                data = json.load(f)
                self.nodes = set(data['nodes'])
        except:
            pass

    def register_node(self, address: str) -> None:
        """
        注册添加一个节点
        :param address: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        f = open(filepath + self.node_file, 'w')
        f.write(json.dumps({
            'nodes': list(self.nodes)
        }))
        f.close()

    def valid_chain(self, chain: List[Dict[str, Any]]) -> bool:
        """
        验证区块链
        :param chain: A blockchain
        :return: True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # print(f'{last_block}')
            # print(f'{block}')
            # print("\n-----------\n")
            # 验证区块的hash值
            if block['previous_hash'] != self.hash(last_block):
                return False

            # 验证工作量证明是否正确
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self) -> bool:
        """
        共识算法解决冲突
        使用网络中最长的链.
        :return:  如果链被取代返回 True, 否则为False
        """

        neighbours = self.nodes
        new_chain = None

        # 最长链的长度为max_length
        max_length = self.length

        # 获取并验证区块链网络中所有节点的链
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 若长度更长并且通过验证，更新max_length和new_chain
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 若发现更长的链，用该链将自己的链替换掉
        if new_chain:
            self.chain = new_chain
            self.length = max_length
            return True

        return False

    def new_block(self, proof: int, previous_hash: Optional[str], miner) -> Dict[str, Any]:
        """
        生成新块
        :param proof: 计算得到的随机数
        :param previous_hash: 前一个区块的hash值
        :return: 新区块
        """

        reports = []
        # 获取确认数大于等于2的记录
        for current in self.current_reports:
            if len(current['confirm']) >= 1:
                reports.append(current)

        # 将确认数大于等于2的记录从current_reports中去除
        for report in reports:
            self.current_reports.remove(report)

        block = {
            'index': len(self.chain) + 1,
            'timestamp': int(round(time() * 1000)),
            'reports': reports,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'miner': miner,
        }

        # 将新块加入区块链
        self.chain.append(block)
        self.length += 1

        # 修改temp文件
        f = open(filepath + self.temp_file, 'w')
        f.write(json.dumps({
            'temp': self.current_reports
        }))
        f.close()

        # 修改data文件
        f = open(filepath + self.chain_file, 'w')
        f.write(json.dumps({
            'chain': self.chain,
            'length': self.length,
        }))
        f.close()

        return block

    def new_transaction(self, number: str, name: str, sj_company: str, wt_company: str, kind: str, path: str, creator: str, timestamp) -> int:
        """
        生成新交易信息，信息将加入到下一个待挖的区块中
        :param sender: 发送者ip地址
        :param recipient: 接收者ip地址
        :param amount: 交易数量
        :return: 待挖区块的index值
        """
        self.current_reports.append({
            'number': number,
            'name': name,
            'sjCompany': sj_company,
            'wtCompany': wt_company,
            'kind': kind,
            'filePath': path,
            'creator': creator,
            'timestamp': timestamp,
            'confirm': []
        })

        f = open(filepath + self.temp_file, 'w')
        f.write(json.dumps({
            'temp': self.current_reports
        }))
        f.close()

        return self.last_block['index'] + 1

    @property
    def last_block(self) -> Dict[str, Any]:
        return self.chain[-1]

    @staticmethod
    def hash(block: Dict[str, Any]) -> str:
        """
        生成区块的 SHA-256 hash值
        :param block: 区块
        """

        # 进行hash计算前，要将区块中的字典排序，否则，顺序不同生成的hash值是不一样的
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof: int) -> int:
        """
        简单的工作量证明:
         - 查找一个 p' 使得 hash(pp') 以4个0开头
         - p 是上一个块的证明,  p' 是当前的证明
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof: int, proof: int) -> bool:
        """
        验证证明: 是否hash(last_proof, proof)以4个0开头

        :param last_proof: Previous Proof
        :param proof: Current Proof
        :return: True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# 实例化节点
app = Flask(__name__)

filepath = '/home/nsy1994/blockchain/'
info_file = 'info.json'
pdf_path = os.path.join(filepath, 'reports')

if not os.path.exists(filepath):
    os.makedirs(filepath)

try:
    # 取出节点地址
    with open(filepath + info_file, 'r') as file:
        node_identifier = json.load(file)['id']
except:
    # 若不存在，为此节点生成全局唯一地址
    node_identifier = str(uuid4()).replace('-', '')
    file = open(filepath + info_file, 'w')
    file.write(json.dumps({
        'id': node_identifier
    }))
    file.close()

# 实例化区块链
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # 挖矿接口
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 生成新区块
    block = blockchain.new_block(proof, None, node_identifier)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'reports': block['reports'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
        'timestamp': block['timestamp'],
        'miner': block['miner'],
    }
    return jsonify(response), 200


@app.route('/reports/new', methods=['POST'])
def new_transaction():
    """
    添加新数据接口
    :return:
    """
    values = request.get_json()

    # 检查POST数据
    required = ['number', 'name', 'sjCompany', 'wtCompany', 'kind', 'filePath', 'nodeId', 'timestamp']
    if not all(k in values for k in required):
        response = {
            'message': 'missing values',
        }
        return jsonify(response), 400

    # 添加一个新的报告信息
    blockchain.new_transaction(values['number'], values['name'], values['sjCompany'], values['wtCompany'],
                               values['kind'], values['filePath'], values['nodeId'], values['timestamp'])

    response = {
        'message': 'add new transaction success',
    }
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    """
    查看整个区块链接口
    :return:
    """
    response = {
        'chain': blockchain.chain,
        'length': blockchain.length,
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    """
    节点注册接口
    :return:
    """
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    """
    解决冲突接口
    :return:
    """
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


# api for cms

# 获取区块链中的检验报告
def return_query_report():
    reports = []
    total = 0
    for block in blockchain.chain:
        for report in block['reports']:
            # 拷贝给data，使得data添加元素不影响blockchain.chain
            data = report.copy()
            data['block'] = block['index']
            reports.append(data)
            total += 1
    reports.reverse()
    response = {
        'list': reports,
        'pagination': {
            'total': total,
            'pageSize': 10,
        }
    }
    return response


# 获取未加入到区块链中的检验报告
def return_query_confirm():
    with open(filepath + blockchain.temp_file, 'r') as f:
        data = json.load(f)['temp']
    data.reverse()
    response = {
        'list': data,
        'pagination': {
            'total': len(data),
            'pageSize': 10,
        }
    }
    return response


@app.route('/cms/queryInfo', methods=['GET'])
def query_info():
    return jsonify({
        'nodeId': node_identifier
    }), 200


@app.route('/cms/report/query', methods=['GET'])
def query_report():
    number = request.args.get('number')
    name = request.args.get('name')
    reports = []
    total = 0
    if number or name:
        for block in blockchain.chain:
            for report in block['reports']:
                if report['number'] == number or report['name'] == name:
                    # 拷贝给data，使得data添加元素不影响blockchain.chain
                    data = report.copy()
                    data['block'] = block['index']
                    reports.append(data)
                    total += 1
    else:
        for block in blockchain.chain:
            for report in block['reports']:
                # 拷贝给data，使得data添加元素不影响blockchain.chain
                data = report.copy()
                data['block'] = block['index']
                reports.append(data)
                total += 1
    reports.reverse()
    response = {
        'list': reports,
        'pagination': {
            'total': total,
            'pageSize': 10,
        }
    }
    return jsonify(response), 200


@app.route('/cms/report/add', methods=['POST'])
def add_report():
    values = request.get_json()

    # 检查POST数据
    required = ['number', 'name', 'sjCompany', 'wtCompany', 'kind', 'filePath']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # 时间戳保留13位，round()是四舍五入
    timestamp = int(round(time() * 1000))

    blockchain.new_transaction(values['number'], values['name'], values['sjCompany'], values['wtCompany'],
                               values['kind'], values['filePath'], node_identifier, timestamp)
    data = {
        'number': values['number'],
        'name': values['name'],
        'sjCompany': values['sjCompany'],
        'wtCompany': values['wtCompany'],
        'kind': values['kind'],
        'filePath': values['filePath'],
        'nodeId': node_identifier,
        'timestamp': timestamp,
    }
    nodes = blockchain.nodes
    for node in nodes:
        try:
            requests.post(f'http://{node}/reports/new', data)
        except:
            continue

    return jsonify(return_query_report()), 201


@app.route('/report/upload', methods=['POST'])
def upload_report():
    pdf_file = request.files.get("file")
    timestamp = str(round(time() * 1000))
    name = os.path.join(timestamp + '-' + pdf_file.filename)
    pdf_file.save(os.path.join(pdf_path, name))
    response = {
        'message': name
    }
    return jsonify(response), 201


@app.route('/report/download/<name>', methods=['GET'])
def download_report(name=None):

    return send_from_directory(directory=pdf_path, filename=name), 200


@app.route('/cms/confirm/query', methods=['GET'])
def upload_confirm():

    return jsonify(return_query_confirm()), 200


@app.route('/cms/confirm/confirm', methods=['POST'])
def confirm():
    values = request.get_json()

    for current in blockchain.current_reports:
        if current['timestamp'] == values['timestamp']:
            current['confirm'].append(values['nodeId'])
            break

    f = open(filepath + blockchain.temp_file, 'w')
    f.write(json.dumps({
        'temp': blockchain.current_reports
    }))
    f.close()

    return jsonify(return_query_confirm()), 201


@app.route('/cms/user/queryInfo', methods=['GET'])
def info():
    mine_num = 0
    create_num = 0
    confirm_num = 0
    for block in blockchain.chain:
        if block['miner'] == node_identifier:
            mine_num += 1
            for report in block['reports']:
                if report['creator'] == node_identifier:
                    create_num += 1
                if node_identifier in report['confirm']:
                    confirm_num += 1
    response = {
        'id': node_identifier,
        'mineNum': mine_num,
        'createNum': create_num,
        'confirmNum': confirm_num,
    }
    return jsonify(response), 200


@app.route('/cms/user/queryBlock', methods=['GET'])
def block():
    index = int(request.args.get('index'))
    if index > blockchain.length:
        index = 0
    return jsonify(blockchain.chain[index-1]), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
